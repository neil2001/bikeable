# Frontend

The frontend is a single-page React + TypeScript map planner. It lives in [`frontend/`](../frontend/) and talks to the FastAPI backend through a Vite `/api` proxy.

There is no router and no global store: [`Planner`](../frontend/src/components/Planner.tsx) plus [`usePlanner`](../frontend/src/hooks/usePlanner.ts) own the session.

## Stack

| Piece | Choice |
| --- | --- |
| UI | React 19, TypeScript |
| Build | Vite 8, `@vitejs/plugin-react` |
| Map | MapLibre GL |
| Charts | Recharts |
| Icons | lucide-react |
| Lint | Oxlint (`npm run lint`) |

No CSS framework. Tokens live in [`frontend/src/index.css`](../frontend/src/index.css); layout in [`frontend/src/App.css`](../frontend/src/App.css).

## Layout

```text
frontend/src/
├── main.tsx                 React root (StrictMode)
├── App.tsx                  Renders <Planner />
├── api/                     Fetch wrappers, error envelope, optional mocks
├── components/              Planner shell, controls, summary, charts, inspector, legend
├── hooks/usePlanner.ts      Modes, waypoints, selected roads, API calls
├── planner/                 Waypoint helpers for the unified Plan mode
├── units.ts                 Display formatters and unit preference storage
├── map/                     MapLibre view, style, colors, trace helpers
└── types/api.ts             CamelCase types matching the backend
```

## Run

```bash
cd frontend
npm ci
npm run dev          # http://localhost:5173
```

Vite proxies `/api` to `API_PROXY_TARGET` or `http://127.0.0.1:8000` ([`vite.config.ts`](../frontend/vite.config.ts)).

Env:

| Variable | Default | Meaning |
| --- | --- | --- |
| `VITE_API_MODE` | `live` | `mock` uses in-memory Vancouver fixtures for a subset of calls |
| `VITE_DEFAULT_CITY_ID` | `vancouver` | Initial city id |
| `API_PROXY_TARGET` | `http://127.0.0.1:8000` | Dev-server proxy target (not a Vite `VITE_` var) |

Docker Compose sets `API_PROXY_TARGET=http://backend:8000` and `VITE_API_MODE=live`.

Mock mode only covers health, cities, bikeability overlay, and loop generation. Plan routing, road inspect, and GPX still hit the network.

## API client

[`frontend/src/api/client.ts`](../frontend/src/api/client.ts) wraps:

| Function | Backend |
| --- | --- |
| `getHealth` | `GET /api/v1/health` |
| `getCities` | `GET /api/v1/cities` |
| `getBikeabilityNetwork` | `GET /api/v1/cities/{id}/bikeability` |
| `inspectRoad` | `GET /api/v1/roads/{id}` |
| `routeSegment` / `routeManual` | Plan-mode routing |
| `routeFromRoads` | Rebuild a path from `roadIds` |
| `traceExtend` | Grow a Plan selection |
| `generateLoop` | Auto loop |
| `downloadGpx` | GPX blob |

Failures parse `{ error: { code, message, details } }` into `ApiClientError` ([`api/errors.ts`](../frontend/src/api/errors.ts)).

## Planner modes

[`usePlanner`](../frontend/src/hooks/usePlanner.ts) modes: `manual` | `auto`. The panel tabs Plan / Generate / Settings map onto those (`Settings` does not change mode).

Shared state: city, bikeability vs distance weight (default 80% bikeable), target loop distance stored as meters (default ~30 mi), current `RouteResponse`, loading/error, road inspection.

Display units default to **imperial** (mi, ft, mph). The Settings tab toggles **metric** (km, m, km/h); the choice is saved in `localStorage` under `bikeable.unitSystem`. The API always uses meters and kph; only labels and formatters change.

Switching mode or city clears the route, selected roads, and waypoints.

### Plan (`manual`)

One workflow that used to be split across Plan and Trace. Clicks always grow the route **forward** from the current end:

1. Hit-test overlay features (12 px box so hairline roads register).
2. Inspect the clicked `roadId` (street name feeds the stop list).
3. [`detectTraceClick`](../frontend/src/map/tracePath.ts) decides undo-last (click the last segment), ignore (middle of path), or extend.
4. Extend calls `POST /routes/trace-extend` with the clicked road. Same-name streets skip ahead along the corridor; a new street gets a bikeable connector, then that street.
5. Empty-map clicks drop a start (first click) or extend to that coordinate.
6. Stops are small numbered map pins plus a sidebar list (delete, drag to reorder, click to focus). Dragging a pin reroutes between remaining stops. Undo last / Clear restore prior snapshots.

Overlay features are **undirected** (one LineString per two-way street). Directed ids `source:target:key` are recovered by trying the clicked id and its reverse (`highlightRoadIds`).

### Generate (`auto`)

Click the map to set a start (`S` marker, draggable). **Generate route** calls `generateLoop` with the target distance in meters (from the Generate input, converted from mi or km) and ±15% distance constraints.

## Map

[`MapView`](../frontend/src/map/MapView.tsx):

- Basemap: OpenFreeMap Positron (`https://tiles.openfreemap.org/styles/positron`).
- Source `bikeability`: GeoJSON from `getBikeabilityNetwork`, restyled by score (grey → amber → green → teal) with zoom-scaled width/opacity so dense cities do not fill in as a blob.
- Filter: legend dual-range 0–10.
- Source `route`: white casing + blue line (`#2563eb`).
- Layer `traced-roads`: thicker blue highlight of selected overlay ids.
- Camera: fit city bbox on city change; fit route bounds when a new path arrives (padding leaves room for the side panel).

MapLibre needs WebGL. Headless / GPU-less environments often show a blank canvas even when the API overlay loaded.

[`cursorDistanceM`](../frontend/src/components/RouteCharts.tsx) from chart hover is passed into `MapView` but is not drawn on the map.

## UI pieces

| Component | Role |
| --- | --- |
| `Planner` | Full-screen map, floating header, collapsible side panel, heatmap legend |
| `RouteControls` | Tabs, city, mode-specific actions, units toggle, locate, export GPX |
| `WaypointList` | Plan-mode stops: reorder, delete, focus |
| `RouteSummary` | Distance, average bikeability / 10, elevation gain, % high quality (units from Settings) |
| `RouteCharts` | Elevation and bikeability vs distance (hides elevation if all samples are null; axes follow Settings units) |
| `RoadInspector` | Score, highway, speed, surface, protected infra, scoring reasons (speed follows Settings units) |
| `BikeabilityLegend` | Toggle overlay + min/max filter |

On narrow viewports the panel becomes a bottom sheet ([`App.css`](../frontend/src/App.css)).

## Bikeability colors

[`map/colors.ts`](../frontend/src/map/colors.ts) splits 0–10 into thirds:

- 0–~3.3 poor (slate)
- ~3.3–~6.7 moderate (amber)
- ~6.7–10 good / excellent (green → teal)

Keep in sync with CSS `--accent` / `--route`.

## Tests

There is no frontend unit-test runner. Quality gates:

```bash
cd frontend
npm run lint
npx tsc -b --pretty false
npm run build
```

Root `make test` runs the production build; `make lint` runs Oxlint + `tsc`.

## Limitations

- Default city is `vancouver`. Without a processed graph the overlay/routing APIs return 503 (the backend may fall back to fixture for some route calls).
- Heatmap GeoJSON for a full metro is large; the overlay is already collapsed to undirected features to keep MapLibre usable.
- Partial mock API — do not expect Plan routing to work with `VITE_API_MODE=mock` alone.
- Chart cursor does not appear on the map.
