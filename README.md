# Bikeable

Map-first cycling planner: score OSM streets for bikeability, then build a route that prefers those streets over a shortest-time path.

```text
OpenStreetMap → features → 0–10 score → weighted graph → Plan / Generate → map + GPX
```

The UI is a React + MapLibre planner. The API is FastAPI + NetworkX. Cities today: **Vancouver metro** (needs a built graph) and an in-memory **fixture** network used by tests.

## Repo

```text
backend/           FastAPI app (uv)
frontend/          Vite + React + MapLibre
config/scoring/    Bikeability YAML (v2 is active)
data/              Raw OSM extracts, processed graphs (gitignored)
scripts/           Graph build CLI
documentation/     Implementation notes
```

Deeper detail:

- [Backend implementation](documentation/backend.md)
- [Frontend implementation](documentation/frontend.md)

Product/engineering spec (longer, forward-looking): [`plans/spec.md`](plans/spec.md).

## Quick start

Needs Python 3.11+ (3.13 in Docker), [uv](https://docs.astral.sh/uv/), Node 22, and optionally Docker.

### Native

```bash
# API
cd backend && uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# UI (another terminal)
cd frontend && npm ci
API_PROXY_TARGET=http://127.0.0.1:8000 VITE_API_MODE=live npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite dev server proxies `/api` to port 8000.

Without a Vancouver extract the overlay for `vancouver` is unavailable. Tests and Plan still work against `cityId=fixture`.

### Docker

```bash
make dev          # docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000 (`/api/v1/health`, OpenAPI at `/docs`)

Compose bind-mounts `backend/`, `frontend/`, `config/`, and `data/`. Put secrets in a repo-root `.env` (not committed).

### Cloud Agent

[`.cursor/environment.json`](.cursor/environment.json) installs uv + npm deps and starts both servers on 8000 / 5173.

## Build the Vancouver graph

Processed graphs are not in git (`data/processed/**` is ignored).

```bash
make build-graph
# or: cd backend && uv run python ../scripts/build_city_graph.py vancouver [--osm path]
```

Uses `data/raw/vancouver.osm` / `.osm.pbf` if present, otherwise a bbox extract (Overpass/OSMnx). PBF clipping needs [osmium](https://osmcode.org/osmium-tool/).

## Planner modes

| Tab | Behavior |
| --- | --- |
| **Plan** | Click a road to follow it. Same street traces along it; a new street routes there. Empty-map clicks drop stops. Stops appear in the sidebar. |
| **Generate** | Click a start, set a distance, generate a loop. |
| **Settings** | Units (mi/ft vs km/m), heatmap opacity, and bikeability vs shortness weight. |

Bikeability scoring uses a single calibrated weight set in [`config/scoring/v2.yaml`](config/scoring/v2.yaml).

## Tests and lint

```bash
make test         # backend pytest + frontend production build
make lint         # ruff + oxlint + tsc
```

Or separately: `cd backend && uv run pytest`; `cd frontend && npm run lint && npm run build`.

## API sketch

Prefix `/api/v1`. JSON is camelCase.

- `GET /health`, `GET /cities`, `GET /cities/{id}/bikeability/tiles/{z}/{x}/{y}.pbf`
- `GET /roads/{roadId}`
- `POST /routes/segment`, `/routes/manual`, `/routes/from-roads`, `/routes/trace-extend`, `/routes/loop`
- `GET /routes/{routeId}`, `GET /routes/{routeId}/gpx`

See [documentation/backend.md](documentation/backend.md) for request bodies and error codes.
