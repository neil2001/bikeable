# Backend

The backend is a FastAPI service that turns an OpenStreetMap street graph into scored bikeable edges, then builds routes from those edges. It lives in [`backend/`](../backend/) and is packaged as `bikeable-backend` (`requires-python >= 3.11`).

Pipeline in one line:

**OSM extract → NetworkX graph → road features → bikeability score → weighted routing / trace / loop → GeoJSON or GPX**

## Stack

| Piece | Choice |
| --- | --- |
| HTTP | FastAPI + Uvicorn |
| Graphs | NetworkX, OSMnx |
| Config | pydantic-settings, PyYAML |
| Tooling | uv (`uv.lock`), Ruff, pytest |

Docker image: `python:3.13-slim` with uv copied in ([`backend/Dockerfile`](../backend/Dockerfile)).

## Layout

```text
backend/app/
├── main.py              FastAPI app, GZip, CORS, exception handlers
├── config.py            Settings from env / repo .env
├── api/                 Routers: health, cities, roads, routes
├── models/              Request/response models (camelCase JSON)
├── graph/               Ingest, store, fixture, geometry, QA, city registry
├── features/            OSM tags → RoadFeatures on each edge
├── scoring/             YAML v2 model, score_graph, bike_graph
├── routing/             Costs, snap, Dijkstra, metrics, trace, road IDs
├── optimization/        Loop heuristic
├── elevation/           Open-Meteo client + null fallback
├── export/              GPX
└── services/            Facades: city graph cache, overlay, inspect, route store
```

Related repo paths:

- [`config/scoring/v2.yaml`](../config/scoring/v2.yaml) — active scoring config
- [`data/processed/`](../data/processed/) — cached graphs and overlays (gitignored)
- [`scripts/build_city_graph.py`](../scripts/build_city_graph.py) — one-city graph build

## Runtime

[`backend/app/main.py`](../backend/app/main.py) mounts routers under `/api/v1`, compresses responses larger than 1 KB, and allows CORS from `CORS_ORIGINS` (default `http://localhost:5173`).

Errors are a JSON envelope:

```json
{ "error": { "code": "GRAPH_UNAVAILABLE", "message": "...", "details": {} } }
```

Codes: `INVALID_REQUEST`, `INVALID_COORDINATES`, `CITY_NOT_AVAILABLE`, `ROUTE_NOT_FOUND`, `DISTANCE_CONSTRAINT_UNSATISFIABLE`, `GRAPH_UNAVAILABLE`, `ROUTE_GENERATION_FAILED`, `INTERNAL_ERROR`.

### Settings

[`backend/app/config.py`](../backend/app/config.py) (env file is the repo-root `.env`):

| Setting | Default |
| --- | --- |
| `app_name` | `Bikeable Route Finder` |
| `cors_origins` | `http://localhost:5173` |
| `scoring_config_path` | `config/scoring/v2.yaml` |
| `data_root` | `data/` |
| `default_city_id` | `vancouver` |
| `elevation_provider` | `open_meteo` |
| `elevation_api_url` | `https://api.open-meteo.com/v1/elevation` |

Compose also sets `UV_LINK_MODE=copy` so the bind-mounted backend can use the image `.venv`.

## Cities

Two cities are registered in [`backend/app/graph/registry.py`](../backend/app/graph/registry.py):

| `cityId` | Role |
| --- | --- |
| `vancouver` | Metro Vancouver bbox (UBC through North Van). Requires a processed graph. |
| `fixture` | Tiny 4-node graph for tests and local demo. Always available in memory. |

`GET /api/v1/cities` **omits fixture** when a real city graph is available so the picker stays production-oriented. If no real graph is built, fixture is included so the planner can still be used. Fixture is always addressable by id. If the requested city’s graph is missing, [`resolve_city_id`](../backend/app/services/city_registry.py) falls back to `fixture`.

Until you run `make build-graph`, Vancouver reports `graphVersion: "unbuilt"` and bikeability/routing against it return `503 GRAPH_UNAVAILABLE` (or silently use fixture when resolving).

## API

JSON uses camelCase. Route/road query `cityId` defaults to `fixture` on the HTTP layer (distinct from settings `default_city_id=vancouver`).

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Liveness `{ status: "ok" }` |
| `GET` | `/api/v1/cities` | City list (no fixture) |
| `GET` | `/api/v1/cities/{cityId}` | One city summary + bbox |
| `GET` | `/api/v1/cities/{cityId}/bikeability/tiles/{z}/{x}/{y}.pbf` | Vector tile (MVT) overlay + ETag |
| `GET` | `/api/v1/roads/{roadId}?cityId` | Inspect one edge |
| `POST` | `/api/v1/routes/segment` | Shortest bikeable path between two points |
| `POST` | `/api/v1/routes/manual` | Chain waypoint pairs; store route |
| `POST` | `/api/v1/routes/from-roads` | Assemble a walk from ordered `roadIds` |
| `POST` | `/api/v1/routes/trace-extend` | Grow a Plan path from a clicked road or coordinate |
| `POST` | `/api/v1/routes/loop` | Distance-constrained loop from a start |
| `GET` | `/api/v1/routes/{routeId}` | Recall a stored route |
| `GET` | `/api/v1/routes/{routeId}/gpx` | GPX 1.1 download |

Preferences `{ distanceWeight, bikeabilityWeight }` must sum to 1. Stored routes live in a **process-local dict** ([`route_store.py`](../backend/app/services/route_store.py)) — they vanish on restart.

Road IDs are `"source:target:key"` directed NetworkX edge keys ([`backend/app/routing/ids.py`](../backend/app/routing/ids.py)).

## Graph pipeline

1. **Extract** ([`graph/ingest.py`](../backend/app/graph/ingest.py), [`graph/extract.py`](../backend/app/graph/extract.py)): prefer `data/raw/{city}.osm` / `.osm.pbf`, or clip a regional PBF with osmium; otherwise download via OSMnx/Overpass for the city bbox.
2. **Filter**: keep bikeable ways; drop motorways and private; annotate park proximity (`in_park`).
3. **Features** ([`features/`](../backend/app/features/)): normalize OSM tags into `RoadFeatures` (infrastructure class, traffic/speed/surface/grade comfort, calm geometry, traversable flag). Traffic is usually **imputed** from highway/lanes/speed — there is no live AADT feed.
4. **Persist** under `data/processed/{cityId}/` as GraphML + pickle + `metadata.json` + `qa.json`. Graph store version is currently **4**.

Build:

```bash
make build-graph
# or: cd backend && uv run python ../scripts/build_city_graph.py vancouver [--osm path]
```

Fixture graphs are generated in tests (`tiny_graph.graphml`); do not build `fixture` with the script.

## Scoring (v2)

Active file: [`config/scoring/v2.yaml`](../config/scoring/v2.yaml). [`v1.yaml`](../config/scoring/v1.yaml) is leftover linear weights and is not loaded by default.

For each edge ([`scoring/score.py`](../backend/app/scoring/score.py)):

1. Base score in `[0, 1]` — weighted mean of known components (`traffic`, `speed`, `road_environment`, `surface`, `calm_geometry`, `grade`). Missing optional dimensions are dropped and weights renormalized. Grade weight is **0**.
2. Infrastructure bonus (cycleway / track / lane / …), capped.
3. Context bonus (park / greenway / LCN), scaled, capped.
4. Interaction terms (calm combo, park+calm, exposed fast/wide, protection on busy roads).
5. Final score clamped to **0–10**, stored on the edge as `bikeability`.

[`create_bike_graph`](../backend/app/scoring/bike_graph.py) copies the scored graph, drops non-traversable edges (including unmarked sidewalks and private driveways on the overlay), and can keep walk links marked `walk_link=True`. Unmarked pedestrian ways are kept for routing only when they are high-detour necessary connectors; other walk highways with `bicycle=no` may still be walk links.

Routing cost ([`routing/cost.py`](../backend/app/routing/cost.py)):

`length * (distanceWeight + bikeabilityWeight * (1 - score/10)^gamma)` with extra penalty when score is below `avoid_score`. Walk links are multiplied by a large factor so they are last-resort connectors.

## Routing modes

**Point-to-point** ([`routing/point_to_point.py`](../backend/app/routing/point_to_point.py)): snap start/end to the nearest edge via the routing index (max 250 m), then NetworkX weighted shortest path using an on-the-fly cost callback (no per-request graph copy). This is Plan-mode waypoint routing.

**From-roads**: validate that `roadIds` form a directed walk (with reverse / osmid / skip-edge resolution), concatenate geometries, compute metrics. No shortest-path search.

**Trace-extend** ([`routing/trace.py`](../backend/app/routing/trace.py)): given the current selection and a clicked overlay `roadId` (or a map coordinate), grow the path **forward from the current head**. Either start a path, append a connected edge, skip ahead along the same named/osmid street, or insert a short bikeable connector. The first click is oriented so the path starts at the click. Returns an action of `select` | `same_road` | `route` plus an optional `destinationName`.

**Loop** ([`optimization/loop.py`](../backend/app/optimization/loop.py), algorithm `loop-heuristic-v1`): sample nodes near radius `target / 2π`, rank by local bikeability, try multi-waypoint sequences and out-and-backs, keep candidates that satisfy distance (± constraints) and quality limits.

**Metrics** ([`routing/metrics.py`](../backend/app/routing/metrics.py)): distance-weighted average bikeability; `%` high quality (≥ 7); `%` bad (< 5); protected / high-speed fractions; elevation gain from sampled elevations. `hostileIntersections` is always `0`. Route `score` is the average bikeability.

Elevation comes from Open-Meteo when `ELEVATION_PROVIDER=open_meteo`; otherwise samples are `null`. Tests force the null provider via [`backend/tests/conftest.py`](../backend/tests/conftest.py).

## Heatmap overlay

`GET /cities/{id}/bikeability/tiles/{z}/{x}/{y}.pbf` serves **Mapbox vector tiles** from a cached **PMTiles** archive. [`graph_to_bikeability_geojson`](../backend/app/services/bikeability_map.py) builds the overlay (traversable edges, collapsed bidirectional pairs, `roadId` + `bikeability`); [`bikeability_tiles.py`](../backend/app/services/bikeability_tiles.py) encodes MVT zoom 8–14. `make build-graph` prebuilds `bikeability-g{graph}-s{score}-o{format}.pmtiles` next to the processed graph. Tiles use `ETag` / `304`; empty tiles return `204`.

## Tests

From `backend/`:

```bash
uv run pytest
```

Coverage includes health/OpenAPI, features, scoring v2, graph ingest/QA, point-to-point preferences, from-roads, trace-extend, loop+GPX, overlay ETag, city-graph cache, and elevation fallback. The fixture city is the usual test network so CI does not need a Vancouver extract.

## Limitations

- Vancouver graph is not committed; clone + `make build-graph` (needs OSM download or a local PBF, and osmium for PBF clipping).
- Route store is in-memory only.
- First request after an overlay format bump rebuilds PMTiles (slow for a full metro until `make build-graph` is run).
- GPX elevation currently stamps the first known elevation on every trackpoint.
- [`backend/app/routing/session.py`](../backend/app/routing/session.py) is an unfinished A* path and is not used by live routing; [`routing/index.py`](../backend/app/routing/index.py) is used for nearest-edge snap on cached bike graphs.
- Query-string `cityId` defaults to `fixture` while app settings default to `vancouver`.
