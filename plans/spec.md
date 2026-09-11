# Bikeable Route Finder

A system for identifying the most bikeable roads in a city and chaining them into high-quality cycling routes.

The core idea:

> **OpenStreetMap road network → road features → bikeability score → weighted graph → route optimization → GPX**

The project is intended to be implemented by multiple coding subagents, so this README doubles as the technical product/engineering specification.

---

# 1. Product Goal

The system should eventually answer:

> Given a city, starting point, distance target, and cyclist profile, generate a route that maximizes cycling quality rather than merely minimizing travel time or distance.

Examples:

- "Show me the most bikeable roads in Seattle."
- "Find me a 15-mile bike route from here."
- "Generate a 40-mile road-cycling loop."
- "Prefer protected infrastructure and quiet roads."
- "Minimize time on roads with high traffic."
- "Avoid steep climbs."

There are two related problems:

### Point-to-point routing

```text
A → B
```

Find the best cycling route between two locations.

### Route discovery / loop optimization

```text
Start → ... → ... → Start
```

Find a high-quality cycling route under a distance constraint.

The second problem is the more interesting one and should shape the architecture.

---

# 2. High-Level Architecture

```text
                           ┌─────────────────┐
                           │ OpenStreetMap   │
                           └────────┬────────┘
                                    │
                                    ▼
                           ┌─────────────────┐
                           │ Graph Ingestion │
                           │     / OSMnx     │
                           └────────┬────────┘
                                    │
                                    ▼
                           ┌─────────────────┐
                           │ Road Graph      │
                           │ NetworkX        │
                           └────────┬────────┘
                                    │
             ┌──────────────────────┼──────────────────────┐
             │                      │                      │
             ▼                      ▼                      ▼
       OSM Attributes          Traffic Data          Elevation
             │                      │                      │
             └──────────────────────┼──────────────────────┘
                                    ▼
                           ┌─────────────────┐
                           │ Feature Builder │
                           └────────┬────────┘
                                    │
                                    ▼
                           ┌─────────────────┐
                           │ Bikeability     │
                           │ Scoring Model   │
                           └────────┬────────┘
                                    │
                                    ▼
                           ┌─────────────────┐
                           │ Weighted Graph  │
                           └────────┬────────┘
                                    │
                    ┌───────────────┴────────────────┐
                    ▼                                ▼
             Point-to-Point                    Loop Optimizer
                  A*                                  │
                    │                                  │
                    └────────────────┬─────────────────┘
                                     ▼
                            ┌──────────────────┐
                            │ Route Validation │
                            └────────┬─────────┘
                                     ▼
                            ┌──────────────────┐
                            │ GeoJSON / GPX    │
                            └────────┬─────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │ React + TS Map UI│
                            └──────────────────┘
```

---

# 3. Application Architecture

Use a standard monorepo:

```text
bike-route-finder/
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── routes.py
│   │   │   ├── cities.py
│   │   │   └── health.py
│   │   ├── models/
│   │   │   ├── requests.py
│   │   │   └── responses.py
│   │   ├── services/
│   │   │   ├── routing.py
│   │   │   ├── scoring.py
│   │   │   ├── graph.py
│   │   │   └── route_generation.py
│   │   └── config.py
│   └── tests/
│
├── frontend/
│   ├── package.json
│   ├── Dockerfile
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   ├── types/
│   │   ├── map/
│   │   └── App.tsx
│   └── tests/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── cache/
│
├── notebooks/
├── scripts/
├── docker-compose.yml
├── Makefile
└── README.md
```

The backend owns:

- graph ingestion
- graph preprocessing
- bikeability scoring
- routing
- route optimization
- GPX/GeoJSON generation

The frontend owns:

- map interaction
- route configuration
- route visualization
- road-score visualization
- route metadata

---

# 4. Backend

## 4.1 FastAPI

Use FastAPI for the API layer.

Suggested application structure:

```python
# app/main.py

from fastapi import FastAPI

app = FastAPI(title="Bike Route Finder")

app.include_router(route_router, prefix="/api/routes")
app.include_router(city_router, prefix="/api/cities")
```

Keep HTTP concerns out of routing/scoring code.

The API layer should call services:

```text
FastAPI endpoint
    ↓
request validation
    ↓
service
    ↓
graph/routing/scoring logic
    ↓
response model
```

Do not put graph algorithms directly inside route handlers.

---

# 5. Backend Domain Model

The graph should be based around three concepts:

```text
Node
Edge
Route
```

## Node

Represents an intersection or graph point.

Example:

```python
class GraphNode:
    id: int
    lat: float
    lon: float
```

## Edge

Represents a traversable road segment.

Conceptual structure:

```python
class RoadEdge:
    id: str
    source: int
    target: int

    length_m: float

    highway: str | None
    maxspeed_kph: float | None
    lanes: int | None
    surface: str | None

    cycleway: str | None
    bicycle: str | None
    oneway: bool

    grade: float | None

    bikeability: float | None
```

The actual implementation can use NetworkX/OSMnx edge dictionaries rather than custom classes, but the conceptual model should remain this clean.

---

# 6. Graph Ingestion

Use OSMnx to download the street network.

Example:

```python
import osmnx as ox

graph = ox.graph_from_place(
    "Seattle, Washington, USA",
    network_type="bike",
    simplify=True,
)
```

For the first implementation, consider downloading a broader set of streets and filtering/scoring them yourself instead of relying solely on OSMnx's default `bike` network.

The ingestion pipeline should:

1. Download graph.
2. Project coordinates to a suitable metric CRS.
3. Normalize edge attributes.
4. Add derived attributes.
5. Persist the processed graph.
6. Load the graph into memory for routing.

Conceptual pseudocode:

```text
function load_city_graph(city):
    if cached_processed_graph_exists(city):
        return load_graph(city)

    raw_graph = download_osm(city)

    graph = simplify(raw_graph)
    graph = project_to_metric_crs(graph)
    graph = normalize_attributes(graph)
    graph = add_derived_features(graph)

    save_graph(graph)

    return graph
```

---

# 7. Graph Preprocessing

OSM data is messy and should be normalized before scoring.

## Normalize speed

Input can look like:

```text
"30 mph"
"30"
"50"
"signals"
None
```

Normalize everything to a consistent numerical representation.

Example:

```python
def normalize_speed(value):
    if value is None:
        return None

    # parse strings, mph, km/h, lists, etc.
    # return km/h
```

## Normalize lanes

Convert:

```text
"2"
"2;3"
None
```

into a usable representation.

## Normalize cycleway tags

OSM can encode cycling infrastructure in several ways:

```text
cycleway
cycleway:left
cycleway:right
cycleway:both
bicycle
highway=cycleway
```

Build one internal representation such as:

```python
bike_infrastructure = {
    "protected": bool,
    "lane": bool,
    "shared": bool,
    "path": bool,
}
```

The exact representation is an implementation detail; the important requirement is that the scoring layer should not need to understand every raw OSM tag.

---

# 8. Feature Engineering

Create a feature-building layer between raw graph data and scoring.

Example:

```python
@dataclass
class RoadFeatures:
    length_m: float
    highway_class: str | None

    speed_kph: float | None
    lane_count: int | None

    protected_bike_infra: bool
    bike_lane: bool
    shared_lane: bool

    surface_quality: float
    grade: float | None

    traffic_volume: float | None
```

Pseudocode:

```text
function build_features(edge):
    return RoadFeatures(
        length = normalize_length(edge),
        highway_class = normalize_highway(edge),
        speed = normalize_speed(edge),
        lanes = normalize_lanes(edge),
        protected_bike_infra = detect_protected_infra(edge),
        bike_lane = detect_bike_lane(edge),
        shared_lane = detect_shared_lane(edge),
        surface_quality = classify_surface(edge),
        grade = edge.grade,
        traffic_volume = lookup_traffic(edge),
    )
```

This separation lets us add new data sources without rewriting routing.

---

# 9. Bikeability Model

Every edge gets a bikeability score.

Initial range:

```text
0 = extremely hostile
10 = excellent
```

A first model can be a weighted sum:

```text
score =
    infrastructure_score
  + road_type_score
  + speed_score
  + traffic_score
  + surface_score
  + grade_score
  + other_adjustments
```

Normalize/clamp:

```python
score = max(0.0, min(10.0, score))
```

Example:

```python
def score_road(features, profile):
    score = 0.0

    score += infrastructure_score(features, profile)
    score += road_type_score(features, profile)
    score += speed_score(features, profile)
    score += traffic_score(features, profile)
    score += surface_score(features, profile)
    score += grade_score(features, profile)

    return clamp(score, 0.0, 10.0)
```

---

# 10. Recommended Initial Scoring Rules

The exact coefficients should be configurable.

## Infrastructure

Rough ordering:

```text
protected cycle track    → strongest positive
dedicated bike path      → very strong positive
painted bike lane        → strong positive
shared lane              → small positive
sharrows                 → very small positive
no infrastructure       → neutral
```

## Road hierarchy

Typical initial tendency:

```text
living_street   → very good
residential     → very good
service         → good
tertiary        → neutral/good
secondary       → penalty
primary         → larger penalty
trunk           → severe penalty
motorway        → exclude
```

This should not be treated as universally correct. Infrastructure can override road hierarchy.

## Speed

Example starting point:

```text
≤ 25 mph  → little/no penalty
30 mph    → small penalty
35 mph    → medium penalty
40 mph    → large penalty
45+ mph   → very large penalty
```

## Traffic

Traffic should be heavily penalized when data is available.

## Surface

Example:

```text
paved/asphalt → positive
concrete      → positive/neutral
gravel        → configurable
dirt          → strong penalty
cobblestone   → penalty for road cycling profile
```

---

# 11. Cyclist Profiles

Do not hard-code one universal definition of "good."

Support profiles:

```text
road
commuter
leisure
fitness
cargo
```

For example:

```python
@dataclass
class CyclingProfile:
    hill_penalty: float
    traffic_penalty: float
    high_speed_penalty: float
    bad_surface_penalty: float
    protected_infra_bonus: float
```

Example:

```text
road cyclist:
    lower traffic sensitivity
    lower hill penalty
    high surface sensitivity

commuter:
    high traffic sensitivity
    high hill penalty
    high infrastructure preference
```

The same graph can then be scored differently without downloading the city again.

---

# 12. Excluded / Illegal Edges

Some roads should not merely get a bad score.

They should be removed from the bicycle routing graph.

Examples:

```text
motorways
roads explicitly prohibiting bicycles
clearly inaccessible infrastructure
```

Conceptually:

```python
def is_traversable(edge):
    if edge.highway == "motorway":
        return False

    if edge.bicycle == "no":
        return False

    return True
```

Build:

```text
base graph
   ↓
traversability filter
   ↓
bike routing graph
```

Keep the original graph as well, because it is useful for analysis and visualization.

---

# 13. Convert Bikeability to Routing Cost

Routing algorithms minimize cost.

We therefore need to transform:

```text
high bikeability = good
```

into:

```text
low routing cost = good
```

A simple model:

```python
cost = length_m / (bikeability + epsilon)
```

A more aggressive model:

```python
cost = length_m * exp(-alpha * bikeability)
```

However, pure inverse scoring can create pathological routes.

A better production design is to explicitly model a tradeoff:

```text
cost =
    distance_weight * normalized_distance
    + discomfort_weight * discomfort
```

where:

```text
discomfort = 1 - bikeability / 10
```

For example:

```python
discomfort = 1.0 - edge.bikeability / 10.0

edge_cost = (
    distance_weight * edge.length_m
    + discomfort_weight * discomfort * edge.length_m
)
```

The weights should be profile-dependent.

---

# 14. Point-to-Point Routing

Use A* for normal routing.

Conceptual pseudocode:

```text
function route(start, destination, profile):

    graph = get_bike_graph(profile)

    start_node = nearest_node(graph, start)
    end_node = nearest_node(graph, destination)

    path = astar(
        graph,
        start_node,
        end_node,
        weight=edge_cost
    )

    return build_route(path)
```

The route builder should return:

```python
Route(
    geometry=...,
    distance_m=...,
    duration_s=...,
    average_bikeability=...,
    bikeability_percentiles=...,
)
```

Do not make route geometry the only output. The scoring statistics are important for debugging and UI.

---

# 15. Route Score

A route should have its own score separate from individual edge scores.

Example:

```python
def score_route(edges):
    weighted_score = (
        sum(e.bikeability * e.length_m for e in edges)
        / sum(e.length_m for e in edges)
    )

    return weighted_score
```

Also compute:

```text
average bikeability
minimum bikeability
percentage of route ≥ 7
percentage of route ≥ 8
percentage on protected infrastructure
percentage on high-speed roads
elevation gain
number of bad intersections
```

This gives the frontend useful route-quality metrics.

---

# 16. Long Route / Loop Generation

The loop problem should not be implemented as a gigantic brute-force traversal.

Target:

```text
Start
  ↓
good road network
  ↓
high-quality corridors
  ↓
candidate waypoints
  ↓
A* connections
  ↓
candidate loops
  ↓
route scoring
  ↓
best route
```

## Candidate generation

Generate candidate waypoints in a ring around the starting point.

For example, target radius may be:

```text
target_distance / (2π)
```

but use this only as an initial heuristic.

Alternative:

```text
sample N candidate waypoints
    ↓
discard unreachable points
    ↓
rank by local bikeability
```

---

# 17. Loop Generation Pseudocode

```text
function generate_loop(start, target_distance, profile):

    candidate_points = sample_waypoints(
        around=start,
        target_distance=target_distance
    )

    good_points = rank_waypoints(
        candidate_points,
        by=local_bikeability
    )

    candidates = []

    for sequence in candidate_waypoint_sequences(good_points):

        route = connect_waypoints_with_astar(
            start,
            sequence,
            profile
        )

        if route_is_valid(route, target_distance):
            candidates.append(route)

    return best_route(
        candidates,
        objective=route_objective
    )
```

This is intentionally heuristic.

The first implementation should optimize for useful output, not mathematical optimality.

---

# 18. Candidate Route Objective

A candidate loop should maximize something like:

```text
route quality
=
average bikeability
+
good-road bonus
-
bad-road penalty
-
distance deviation penalty
-
intersection penalty
-
profile-specific penalties
```

Example:

```python
def route_objective(route, target_distance):
    distance_error = abs(route.distance_m - target_distance)

    return (
        10.0 * route.average_bikeability
        + 5.0 * route.pct_high_quality
        - 8.0 * route.pct_bad_roads
        - 0.01 * distance_error
        - 2.0 * route.hostile_intersections
    )
```

The constants should live in configuration, not scattered through the code.

---

# 19. Bikeable Network Extraction

A useful analytical feature is:

> "Show me the good cycling network."

Filter edges:

```python
good_edges = [
    edge for edge in graph.edges
    if edge.bikeability >= threshold
]
```

Create a subgraph.

Then find connected components:

```python
components = nx.connected_components(good_graph)
```

This reveals:

- large cycling networks
- isolated excellent roads
- disconnected corridors
- weak connector roads

This is useful both for visualization and for route generation.

---

# 20. Connector Roads

The best route may need to use a mediocre road briefly to connect two excellent networks.

Therefore:

```text
excellent network A
       │
       │ connector
       ▼
excellent network B
```

Do not simply delete every road below the high-quality threshold.

Instead:

```text
Tier 1/2/3:
    preferred

Tier 4:
    connectors

Tier 5:
    avoid unless necessary
```

This distinction is important for realistic route generation.

---

# 21. Intersection Modeling

Later, add node-level penalties.

For each intersection:

```text
lane count
road hierarchy
traffic
crossing width
turning conflicts
signalization
```

Then:

```text
route_cost =
    Σ edge_cost
    + Σ node_cost
```

Potential pseudocode:

```python
def intersection_cost(node):
    if node.is_simple_residential_intersection:
        return 0

    return (
        lane_penalty(node)
        + traffic_penalty(node)
        + crossing_penalty(node)
    )
```

This should be implemented after the edge-scoring MVP works.

---

# 22. External Data Strategy

The system should initially depend only on OSM.

Then add progressively better datasets.

## Stage 1

OpenStreetMap:

```text
road type
speed limit
bike infrastructure
surface
lanes
oneway
access
```

## Stage 2

Elevation:

```text
DEM / elevation data
```

Calculate:

```text
grade
elevation gain
elevation loss
```

## Stage 3

Traffic:

```text
municipal traffic counts
open data
licensed traffic APIs/datasets
```

## Stage 4

Cycling behavior:

```text
permitted GPS traces
actual route choices
```

External data should be modeled behind interfaces so the rest of the backend does not depend on one provider.

Example:

```python
class TrafficProvider(Protocol):
    def get_volume(self, road) -> float | None:
        ...
```

---


# 23. UI / UX Specification

The frontend is a **map-first cycling planner** designed primarily for phone browsers, with a responsive laptop/desktop layout.

The core interaction should feel like:

```text
Open map
   ↓
See bikeability heatmap
   ↓
Tap to place a waypoint
   ↓
Route snaps through the most bikeable path
   ↓
Add more waypoints
   ↓
Inspect route + elevation + bikeability graphs
```

There should also be an automatic route-generation mode:

```text
Choose start
   ↓
Choose target distance
   ↓
Choose cycling profile/preferences
   ↓
Generate loop
   ↓
Inspect route + statistics + graphs
```

The UI should be clean, modern, map-centric, and usable with touch first.

---

# 24. Primary UI Modes

## Mode A — Manual Route Planning

The user explicitly defines the route by dropping waypoints.

```text
Waypoint 1
    ↓
most-bikeable path
    ↓
Waypoint 2
    ↓
most-bikeable path
    ↓
Waypoint 3
```

Each consecutive waypoint pair is automatically connected by the selected bikeability-aware routing policy.

The user should not need to manually draw individual streets.

## Mode B — Automatic Route Generation

The user sets:

```text
Start location
Target distance
Cycling profile
Distance ↔ Bikeability preference
Optional constraints
```

The backend generates a route, ideally as a loop returning near the start.

---

# 25. Desktop Layout

For laptop browsers, use a map-dominant two-panel layout.

```text
┌──────────────────────────────────────────────────────────────┐
│ Bike Route Finder                              [Profile]     │
├─────────────────────────────────────────────┬────────────────┤
│                                             │  ROUTE         │
│                                             │                │
│                   MAP                       │  30.4 mi       │
│                                             │  8.4 / 10      │
│       bikeability heatmap                   │  +1,200 ft     │
│                                             │                │
│            ╭──────────────╮                 │  [Generate]    │
│           ╱                ╲                │                │
│          ╱                  ╲               │  Elevation     │
│         ╰────────────────────╯              │  ╱╲            │
│                                             │ ╱  ╲__/\       │
│                                             │                │
│                                             │  Bikeability   │
│                                             │ ══╲___╱══      │
└─────────────────────────────────────────────┴────────────────┘
```

The map should occupy most of the viewport.

The side panel contains route controls and analytics.

---

# 26. Mobile Layout

Phone browsers should use a map-first bottom-sheet model.

```text
┌──────────────────────────────┐
│                              │
│                              │
│             MAP              │
│                              │
│      bikeability heatmap     │
│                              │
│          ●                   │
│         ╱                    │
│        ╱                     │
│       ●                      │
│                              │
│                     [+]      │
│                              │
├──────────────────────────────┤
│  30.4 mi   8.4/10   +1.2k'  │
│                              │
│  [Plan]       [Details]      │
│                              │
│  swipe up for controls/info  │
└──────────────────────────────┘
```

The collapsed bottom sheet should show only the most important route information.

Swiping upward expands:

```text
route controls
route statistics
elevation chart
bikeability chart
export controls
```

The map should remain available behind the sheet whenever practical.

Avoid making mobile look like a shrunken desktop dashboard.

---

# 27. Map Architecture

The map consists of three conceptual layers:

```text
Base Map
    ↓
Bikeability Layer
    ↓
Route / Waypoint Layer
```

The bikeability layer visualizes the score of every routable road segment.

The route layer is visually dominant over the heatmap.

Waypoints should remain clearly visible over both.

The map library should be isolated behind a small frontend abstraction so swapping MapLibre/Leaflet later does not affect route/planner state.

---

# 28. Bikeability Heatmap

The city-wide bikeability network should be visible as a road heatmap.

Conceptually:

```text
excellent
══════════════════════════

good
──────────────────────────

moderate
--------------------------

poor
··························
```

The visualization should:

- distinguish high and low scores clearly
- remain legible over the base map
- use a route style that is distinct from the road heatmap
- support a legend
- simplify at low zoom levels

At city scale, use vector tiles or an equivalent efficient rendering strategy once raw GeoJSON becomes too large.

At MVP scale, GeoJSON is acceptable.

---

# 29. Bikeability Legend

The map should display a compact legend.

Example:

```text
Bikeability

0 ───── 5 ───── 10
poor          excellent
```

The legend should remain compact on mobile.

The numeric score should never be communicated through color alone.

---

# 30. Road Inspection

Clicking/tapping a road displays a compact inspection card.

Example:

```text
┌─────────────────────────────┐
│ Bikeability     8.6 / 10   │
│                             │
│ Protected bike lane         │
│ 25 mph                      │
│ 2 lanes                     │
│ Asphalt                     │
│ Grade: 1.8%                 │
│                             │
│ Infrastructure       9.8   │
│ Road comfort         8.4   │
│ Speed                8.2   │
│ Traffic              7.9   │
└─────────────────────────────┘
```

This is important for debugging and validating the scoring model.

On mobile, render it as a bottom sheet or floating card with large text and touch-friendly controls.

---

# 31. Manual Waypoint Interaction

The primary manual interaction is:

> **Tap/click the map to place a waypoint.**

After the user adds:

```text
WP1
```

then:

```text
WP2
```

the frontend requests:

```text
route(WP1, WP2)
```

The backend returns the bikeability-optimized segment.

Adding:

```text
WP3
```

requests:

```text
route(WP2, WP3)
```

The displayed route becomes:

```text
WP1 → optimized segment → WP2
                       → optimized segment → WP3
```

This incremental model avoids unnecessarily rerouting unaffected segments.

---

# 32. Waypoint Interaction Details

Each waypoint should have:

```text
visible number
drag affordance
delete action
```

Recommended interactions:

```text
tap empty map
    → add waypoint

drag waypoint
    → move waypoint

tap waypoint
    → show waypoint controls

delete
    → remove waypoint and reconnect affected segments
```

Use a short debounce during dragging:

```text
pointer moves
    ↓
250–500 ms debounce
    ↓
route affected segment
```

Do not issue one API request for every drag event.

Touch targets should be comfortably finger-sized.

---

# 33. Manual Route Editing

When a waypoint moves:

```text
old route
    ↓
identify affected segment(s)
    ↓
reroute only affected segment(s)
    ↓
update displayed route
```

Keep unaffected route segments rendered during the update.

The UI should show that a segment is being recalculated rather than making the entire route disappear.

Once editing settles, request the authoritative complete route metrics from the backend.

---

# 34. Automatic Route Generator UI

Desktop:

```text
┌──────────────────────────────┐
│ Generate a Route             │
│                              │
│ Start                        │
│ [ Pick on map            ]   │
│                              │
│ Distance                     │
│ [ 30 ] mi                    │
│                              │
│ Profile                      │
│ [ Road Cycling ▼ ]           │
│                              │
│ Route preference             │
│ Short ◀──────────────▶ Bikeable │
│                              │
│ [ Generate Route ]           │
└──────────────────────────────┘
```

On mobile, open this control panel as a bottom sheet.

---

# 35. Start Location

Support three input methods:

```text
current browser location
map selection
place/address search
```

The frontend should normalize all three into:

```typescript
type Coordinate = {
  lat: number;
  lon: number;
};
```

The browser geolocation API should only be requested when the user asks to use their location.

---

# 36. Distance Input

Offer common presets:

```text
10 mi
20 mi
30 mi
40 mi
50 mi
```

and allow a custom distance.

Show both:

```text
Target: 30 mi
Generated: 31.2 mi
```

The backend owns the actual feasibility constraints.

---

# 37. Distance ↔ Bikeability Slider

Use a single high-level control:

```text
Shorter / Faster ◀──────────────▶ Most Bikeable
```

Internally:

```text
distanceWeight + bikeabilityWeight = 1
```

Example:

```text
slider = 0.8

distanceWeight = 0.2
bikeabilityWeight = 0.8
```

The frontend sends those two normalized values.

The frontend does not implement the backend's edge-cost equation.

---

# 38. Advanced Constraints

Keep advanced options hidden by default.

Potential controls:

```text
maximum elevation gain
maximum time on high-speed roads
maximum bad-road percentage
minimum bikeability
```

Mobile:

```text
[ Advanced constraints ]
```

expands a secondary sheet/section.

This keeps the primary route-planning flow simple.

---

# 39. Route Summary

When a route exists, always show a compact summary:

```text
30.4 mi
8.4 / 10 bikeability
+1,240 ft
92% high-quality roads
```

Secondary statistics:

```text
31% protected infrastructure
2% bad roads
1% high-speed exposure
4 hostile intersections
```

On desktop these can remain visible in the side panel.

On mobile, show the first four metrics in the collapsed summary and the rest in the expanded details view.

---

# 40. Elevation Graph

Every complete route should include an elevation profile.

```text
Elevation

1600'                    ╭──╮
                        ╱    ╲
1200'       ╭──────────╯      ╲
           ╱                    ╲
 800' ────╯                      ╰──

       0      5      10     15     20 mi
```

Contract:

```json
{
  "elevationProfile": [
    {
      "distanceM": 0,
      "elevationM": 47
    },
    {
      "distanceM": 125,
      "elevationM": 48
    }
  ]
}
```

The frontend owns chart rendering.

The backend owns calculation and sampling.

---

# 41. Bikeability Graph

Display bikeability over cumulative route distance.

```text
Bikeability

10 ┤ ═══════════╲
 8 ┤             ╲════════════
 6 ┤
 4 ┤                     ╲
 2 ┤                      ╲__
 0 ┼──────────────────────────
      0     5    10    15   20 mi
```

Contract:

```json
{
  "distanceM": 0,
  "bikeability": 8.7
}
```

or, preferably, combine it with the elevation samples into one route profile:

```json
{
  "profile": [
    {
      "distanceM": 0,
      "elevationM": 47,
      "bikeability": 8.7
    }
  ]
}
```

Using cumulative distance as the shared x-axis makes linked interactions straightforward.

---

# 42. Linked Graph / Map Interaction

The charts should be synchronized with the route map.

Desktop:

```text
hover graph
    ↓
show vertical graph cursor
    ↓
highlight corresponding map position
```

Mobile:

```text
drag across graph
    ↓
update route position marker on map
```

This should use cumulative route distance rather than attempting to match chart coordinates to map geometry directly.

The interaction allows a rider to immediately answer:

> "Where on the route is this steep climb / low-bikeability section?"

---

# 43. Route Analytics View

Expanded details:

```text
┌───────────────────────────────┐
│ Route quality                 │
│                               │
│ Bikeability          8.4/10  │
│ High-quality roads     92%   │
│ Protected infra        31%   │
│ Bad roads               2%   │
│ High-speed exposure     1%   │
│                               │
│ Elevation                     │
│ +1,240 ft                    │
│                               │
│ Intersections                 │
│ 4 high-stress crossings      │
└───────────────────────────────┘
```

Use progressive disclosure so users see the main route information first.

---

# 44. GPX Export

Once a route exists:

```text
[ Export GPX ]
```

Preferred API:

```http
GET /api/v1/routes/{routeId}/gpx
```

The frontend should not reconstruct the route from map pixels or graph data.

The backend owns the authoritative route geometry and GPX representation.

---

# 45. Loading Behavior

Routing may take time, especially loop generation.

Point-to-point:

```text
Routing...
```

Automatic generation:

```text
Finding a route...
Evaluating candidate routes...
```

The map should remain interactive where possible.

For incremental manual routing, only the affected segment should show a loading state.

The UI should never appear frozen while waiting for the API.

---

# 46. Error Handling

Consistent backend error shape:

```json
{
  "error": {
    "code": "ROUTE_NOT_FOUND",
    "message": "No valid cycling route could be constructed.",
    "details": {
      "reason": "destination_unreachable"
    }
  }
}
```

The frontend branches on:

```text
error.code
```

not on the human-readable message.

Useful states:

```text
ROUTE_NOT_FOUND
DISTANCE_CONSTRAINT_UNSATISFIABLE
CITY_NOT_AVAILABLE
INVALID_REQUEST
```

Use clear user-facing language such as:

```text
No route could be generated within 30–35 miles.
Try increasing the distance range.
```

Never show backend stack traces.

---

# 47. Responsive Design Requirements

Primary target:

```text
phone browser
```

Secondary target:

```text
laptop browser
```

Mobile requirements:

```text
map-first
touch-first
bottom-sheet controls
large touch targets
minimal persistent UI
progressive disclosure
```

Desktop requirements:

```text
map + side panel
hover interactions
keyboard support
more simultaneous analytics
```

Use one responsive application rather than separate desktop/mobile codebases.

---

# 48. Accessibility

Support:

```text
keyboard navigation
screen-reader labels
sufficient contrast
large touch targets
non-color-only indicators
```

Charts should have textual summaries:

```text
Elevation gain: 1,240 ft.
Maximum grade: 9.2%.

Average bikeability: 8.4 / 10.
Lowest bikeability section: 5.1 / 10.
```

Map controls should have accessible labels.

---

# 49. Frontend State Model

Suggested planner state:

```typescript
type PlannerState = {
  mode: "manual" | "auto";

  waypoints: Coordinate[];

  start: Coordinate | null;

  targetDistanceM: number | null;

  profile: CyclingProfile;

  preferences: RoutePreferences;

  constraints: RouteConstraints;

  route: RouteResponse | null;

  selectedRoadId: string | null;

  mapPosition: MapPosition;

  chartCursorDistanceM: number | null;

  loading: boolean;

  error: ApiError | null;
};
```

Server-derived route statistics should not be duplicated into independent state when they can be read from `route`.

The map component should render from application state rather than owning routing logic.

---

# 50. Frontend Component Boundaries

Suggested component tree:

```text
App
├── Planner
│   ├── Map
│   │   ├── BaseMap
│   │   ├── BikeabilityLayer
│   │   ├── RouteLayer
│   │   └── WaypointLayer
│   │
│   ├── RouteControls
│   │   ├── ModeToggle
│   │   ├── StartSelector
│   │   ├── DistanceInput
│   │   ├── ProfileSelector
│   │   ├── PreferenceSlider
│   │   └── AdvancedConstraints
│   │
│   └── RouteDetails
│       ├── RouteSummary
│       ├── ElevationChart
│       ├── BikeabilityChart
│       ├── RouteMetrics
│       └── ExportButton
│
└── RoadInspector
```

Keep API calls inside hooks/services rather than leaf UI components.

Example:

```text
RouteControls
      ↓
useRoute()
      ↓
api/routes.ts
      ↓
FastAPI
```

---

# 51. Frontend ↔ Backend Contract for Manual Planning

Incremental segment routing:

```http
POST /api/v1/routes/segment
```

Request:

```json
{
  "start": {
    "lat": 47.6101,
    "lon": -122.3421
  },
  "end": {
    "lat": 47.6205,
    "lon": -122.3493
  },
  "profile": "road",
  "preferences": {
    "distanceWeight": 0.2,
    "bikeabilityWeight": 0.8
  }
}
```

Response:

```json
{
  "geometry": {
    "type": "LineString",
    "coordinates": []
  },
  "distanceM": 4200,
  "averageBikeability": 8.8,
  "elevationGainM": 42
}
```

This endpoint is optimized for fast incremental edits.

---

# 52. Authoritative Manual Route Contract

For a complete multi-waypoint route:

```http
POST /api/v1/routes/manual
```

Request:

```json
{
  "waypoints": [
    {
      "lat": 47.6101,
      "lon": -122.3421
    },
    {
      "lat": 47.6205,
      "lon": -122.3493
    },
    {
      "lat": 47.6301,
      "lon": -122.3302
    }
  ],
  "profile": "road",
  "preferences": {
    "distanceWeight": 0.2,
    "bikeabilityWeight": 0.8
  }
}
```

Response:

```text
full route geometry
+
authoritative route metrics
+
profile samples
+
routeId
```

Use this endpoint after editing settles or when the user explicitly asks for final route details.

---

# 53. Complete Route Response

The canonical `RouteResponse` should look conceptually like:

```typescript
type RouteResponse = {
  routeId: string;

  geometry: GeoJSON.LineString;

  distanceM: number;
  elevationGainM: number;

  averageBikeability: number;
  pctHighQuality: number;
  pctBadRoads: number;
  pctProtected: number;

  highSpeedExposure: number;
  hostileIntersections: number;

  score: number;

  profile: RouteProfileSample[];

  optimization?: OptimizationMetadata;
};
```

Where:

```typescript
type RouteProfileSample = {
  distanceM: number;
  elevationM: number;
  bikeability: number;
};
```

The backend is authoritative for all calculated route metrics.

---

# 54. API Contract Summary

The frontend needs only stable domain concepts:

```text
Coordinate
CyclingProfile
RoutePreferences
RouteConstraints
RouteResponse
RouteProfileSample
ApiError
```

The frontend does **not** need:

```text
NetworkX node IDs
OSMnx objects
raw OSM tags
graph edge dictionaries
Python classes
routing implementation details
```

The backend should return transport-oriented data that can be rendered directly.

---

# 55. OpenAPI and Generated TypeScript

FastAPI's OpenAPI schema should be the canonical API definition.

Pipeline:

```text
Pydantic models
      ↓
FastAPI
      ↓
OpenAPI
      ↓
generated TypeScript types/client
      ↓
React
```

Once the contract is stable, prefer generated TypeScript types to maintaining independent handwritten request/response interfaces.

This dramatically reduces frontend/backend drift when multiple subagents work concurrently.

---

# 56. Subagent UI Ownership

## Frontend Shell Agent

Owns:

```text
React/Vite setup
routing/page shell
responsive layout
design system primitives
```

## Map Agent

Owns:

```text
Map component
base map
bikeability layer
route layer
waypoints
road inspector
map interaction
```

## Planner Interaction Agent

Owns:

```text
manual waypoints
automatic generation controls
planner state
route hooks
loading/error states
```

## Analytics Agent

Owns:

```text
route summary
elevation chart
bikeability chart
linked graph/map cursor
statistics cards
```

## API Integration Agent

Owns:

```text
typed API client
OpenAPI-generated models
request handling
API error mapping
mock API
```

The agents should communicate through the shared frontend state model and API contract rather than importing internal code from one another.

---

# 57. UI Implementation Milestones

## UI Milestone 1 — Map Shell

- [ ] responsive map
- [ ] base map
- [ ] bikeability network
- [ ] legend
- [ ] map controls

Success criterion:

```text
User can explore a city and understand where good cycling roads are.
```

## UI Milestone 2 — Manual Planner

- [ ] add waypoint
- [ ] move waypoint
- [ ] delete waypoint
- [ ] numbered waypoints
- [ ] incremental segment routing
- [ ] complete-route refresh

Success criterion:

```text
User can build a multi-waypoint route by tapping the map.
```

## UI Milestone 3 — Route Analytics

- [ ] summary metrics
- [ ] elevation chart
- [ ] bikeability chart
- [ ] chart/map synchronization
- [ ] road inspection

Success criterion:

```text
User can understand where the route climbs and where its bikeability drops.
```

## UI Milestone 4 — Automatic Generation

- [ ] start selector
- [ ] distance control
- [ ] profile selector
- [ ] distance/bikeability slider
- [ ] generate route
- [ ] loading/error states

Success criterion:

```text
User can generate a high-quality loop without placing waypoints.
```

## UI Milestone 5 — Mobile Polish

- [ ] bottom sheets
- [ ] touch-friendly waypoints
- [ ] responsive charts
- [ ] browser geolocation
- [ ] mobile-specific interaction tuning

Success criterion:

```text
The planner is comfortable to use from a phone browser.
```

---

# 58. UI Design Direction

The visual style should be:

```text
clean
modern
minimal
map-centric
high signal
low chrome
```

Prefer:

```text
floating controls
compact cards
bottom sheets
large map
progressive disclosure
simple typography
simple charts
```

Avoid:

```text
large permanent nav bars
dense enterprise-dashboard aesthetics
too many controls visible at once
tiny labels
tiny touch targets
heavy borders everywhere
```

The product should feel like a modern navigation/planning application rather than a GIS dashboard.

---

# 59. Complete User Journey

## Manual

```text
Open app
    ↓
See bikeability heatmap
    ↓
Tap → WP1
    ↓
Tap → WP2
    ↓
Bikeability-aware path appears
    ↓
Tap → WP3
    ↓
Another optimized segment appears
    ↓
Move waypoint
    ↓
Affected segment reroutes
    ↓
Open route details
    ↓
Elevation + bikeability graphs
    ↓
Inspect route metrics
    ↓
Export GPX
```

## Automatic

```text
Open app
    ↓
Choose start
    ↓
Choose target distance
    ↓
Choose profile
    ↓
Adjust Shorter/Faster ↔ Most Bikeable
    ↓
Generate route
    ↓
Backend evaluates candidates
    ↓
Route appears on map
    ↓
Inspect metrics + graphs
    ↓
Optionally add waypoints to edit it
    ↓
Export GPX
```

---

# 60. UI / Backend Design Principle

The UI should make the complexity of the routing engine invisible.

The user's mental model is:

```text
I choose where I want to ride.
The system chooses the streets.
```

The frontend owns:

```text
intent
interaction
presentation
```

The backend owns:

```text
road network
bikeability
routing
optimization
route analytics
```

The contract between them should be rich enough to support the entire experience while hiding internal implementation details.

The core UI pipeline remains:

```text
Map
 ↓
Bikeability heatmap
 ↓
Waypoint / Start selection
 ↓
Typed API request
 ↓
Bikeability-aware routing
 ↓
RouteResponse
 ↓
Map + Metrics + Elevation Graph + Bikeability Graph
 ↓
GPX
```


# 23. API Design

Suggested endpoints:

## Get city

```http
GET /api/cities/{city_id}
```

## Generate point-to-point route

```http
POST /api/routes/point-to-point
```

Request:

```json
{
  "start": {
    "lat": 47.61,
    "lon": -122.33
  },
  "end": {
    "lat": 47.64,
    "lon": -122.35
  },
  "profile": "road"
}
```

Response:

```json
{
  "geometry": {
    "type": "LineString",
    "coordinates": []
  },
  "distance_m": 12345,
  "average_bikeability": 8.1,
  "pct_high_quality": 0.91,
  "pct_protected": 0.42,
  "elevation_gain_m": 130
}
```

## Generate loop

```http
POST /api/routes/loop
```

Request:

```json
{
  "start": {
    "lat": 47.61,
    "lon": -122.33
  },
  "target_distance_m": 50000,
  "profile": "road"
}
```

Response should have the same route representation plus optimization metadata.

## Get bikeability map

```http
GET /api/cities/{city_id}/bikeability
```

The response should support efficient map rendering rather than returning millions of raw JSON points.

Eventually use vector tiles or a precomputed GeoJSON representation.

---

# 24. Frontend

Use:

```text
React
TypeScript
Vite
```

The frontend should be map-first.

Suggested structure:

```text
src/
├── api/
│   ├── client.ts
│   └── routes.ts
├── components/
│   ├── Map.tsx
│   ├── RouteControls.tsx
│   ├── RouteSummary.tsx
│   ├── ProfileSelector.tsx
│   └── BikeabilityLegend.tsx
├── hooks/
│   ├── useRoute.ts
│   └── useBikeability.ts
├── types/
│   ├── route.ts
│   └── graph.ts
├── map/
│   ├── layers.ts
│   └── geometry.ts
└── App.tsx
```

---

# 25. Frontend Map

Use a map library such as:

```text
MapLibre
```

or Leaflet.

The map should support:

```text
city view
bikeability overlay
route display
start/end selection
waypoint selection
```

Bikeability visualization:

```text
low score  → visually bad
medium      → neutral
high score  → visually good
```

Avoid tying the backend score model to a particular frontend color scheme.

The frontend receives numeric scores and decides how to render them.

---

# 26. Frontend Route Workflow

Example UI:

```text
┌─────────────────────────────────────────────┐
│ Bike Route Finder                           │
│                                             │
│ Start:  [click map]                         │
│ Distance: [30 mi]                           │
│ Profile:  [Road Cycling ▼]                  │
│                                             │
│ [ Generate Route ]                          │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │                                         │ │
│ │                 MAP                     │ │
│ │                                         │ │
│ │       route                              │ │
│ │      ╱───────╲                          │ │
│ │     ╱         ╲                         │ │
│ │    ╰───────────╯                        │ │
│ │                                         │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ 30.4 mi                                    │
│ 92% high-quality roads                     │
│ 8.1 average bikeability                    │
│ 1,200 ft elevation gain                    │
│                                             │
│ [ Export GPX ]                             │
└─────────────────────────────────────────────┘
```

---

# 27. API Client

Keep API calls typed.

Example:

```typescript
export type RouteRequest = {
  start: Coordinate;
  end?: Coordinate;
  targetDistanceM?: number;
  profile: CyclingProfile;
};

export type RouteResponse = {
  geometry: GeoJSON.LineString;
  distanceM: number;
  averageBikeability: number;
  pctHighQuality: number;
  elevationGainM: number;
};
```

Use a single API client abstraction:

```typescript
export async function generateLoop(
  request: LoopRequest,
): Promise<RouteResponse> {
  const response = await fetch("/api/routes/loop", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error("Failed to generate route");
  }

  return response.json();
}
```

---

# 28. Backend/Frontend Development Workflow

Use Docker Compose for local development.

Conceptually:

```text
docker compose up
       │
       ├── backend :8000
       │
       └── frontend :5173
```

The frontend talks to:

```text
/api/...
```

and Vite proxies those requests to FastAPI during development.

The graph/data pipeline can remain a backend concern.

Do not put OSMnx or NetworkX logic in the frontend.

---

# 29. Data Persistence

The first version does not require Postgres.

Use filesystem-backed processed graph files:

```text
data/
├── raw/
│   └── seattle.osm...
├── processed/
│   ├── seattle.graphml
│   ├── seattle.pkl
│   └── seattle.geojson
└── cache/
```

When the project needs multi-city persistent metadata, concurrent workers, or production-scale serving, add a database later.

For the initial MVP:

```text
filesystem + cached graph
```

is sufficient.

---

# 30. Caching

Graph downloads are expensive and should be cached.

Pseudocode:

```text
function get_graph(city):

    cache_key = hash(city + graph_version)

    if cache_exists(cache_key):
        return cache.load(cache_key)

    graph = build_graph(city)

    cache.save(cache_key, graph)

    return graph
```

Include a scoring-model version in cache keys when necessary:

```text
city
+
graph version
+
scoring version
+
profile
```

This avoids accidentally serving stale scores after changing the scoring logic.

---

# 31. Testing Strategy

Testing should happen at three levels.

## Unit tests

Test:

```text
speed parsing
OSM tag normalization
bikeability scoring
edge cost
route scoring
```

Example:

```python
def test_protected_bike_lane_scores_higher():
    protected = make_features(protected=True)
    none = make_features(protected=False)

    assert score_road(protected, ROAD_PROFILE) > score_road(
        none,
        ROAD_PROFILE,
    )
```

## Integration tests

Test:

```text
OSM graph
    ↓
preprocessing
    ↓
scoring
    ↓
routing
```

Use a tiny fixture graph, not an entire city.

## API tests

Use FastAPI's test client.

---

# 32. Determinism

Route generation should be reproducible.

If candidate waypoint generation uses randomness:

```python
random.seed(seed)
```

Expose a seed internally or in test configuration.

This allows:

```text
same input
+
same graph
+
same scoring version
+
same seed
=
same route
```

That is important for debugging.

---

# 33. Observability

The backend should log:

```text
city
graph version
profile
routing algorithm
route generation parameters
candidate count
generation time
route score
```

For loop generation, useful debug metrics include:

```text
candidate routes generated
candidate routes rejected
reason for rejection
best score
distance error
average bikeability
```

This will make algorithm development much easier.

---

# 34. Performance Considerations

The biggest performance concern will be route optimization, not the FastAPI layer.

## Avoid

Running expensive graph operations repeatedly for every frontend request.

## Prefer

```text
download once
    ↓
preprocess once
    ↓
score once per profile/config
    ↓
keep graph in memory
    ↓
run routing repeatedly
```

For a single-city prototype, a process-local in-memory graph is sufficient.

Later, use workers or precomputed artifacts as necessary.

---

# 35. Implementation Order

The subagents should implement the project in this order.

## Milestone 1 — Repository and Runtime

- [ ] Create monorepo
- [ ] FastAPI backend
- [ ] React + TypeScript frontend
- [ ] Docker Compose
- [ ] Makefile
- [ ] Basic health endpoint
- [ ] Frontend/backend connectivity

Success criterion:

```text
docker compose up

frontend → backend /health
```

---

## Milestone 2 — OSM Graph

- [ ] OSMnx integration
- [ ] city download
- [ ] graph preprocessing
- [ ] metric projection
- [ ] graph caching
- [ ] small-city/sample-city fixture

Success criterion:

```text
load city
→ inspect graph
→ save/load processed graph
```

---

## Milestone 3 — Feature Extraction

- [ ] speed normalization
- [ ] road hierarchy normalization
- [ ] bike infrastructure extraction
- [ ] surface extraction
- [ ] lanes
- [ ] access/bicycle restrictions
- [ ] derived feature model

Success criterion:

```text
Every routable edge has normalized features.
```

---

## Milestone 4 — Bikeability

- [ ] profile definitions
- [ ] scoring functions
- [ ] configurable weights
- [ ] edge scores
- [ ] score distribution diagnostics

Success criterion:

```text
Every routable edge has bikeability ∈ [0, 10].
```

---

## Milestone 5 — Visualization

- [ ] API for bikeability data
- [ ] frontend map
- [ ] score-based road rendering
- [ ] road feature inspection

Success criterion:

```text
Open city map
→ visually inspect bikeability network.
```

This milestone is important because it makes model errors obvious.

---

## Milestone 6 — Point-to-Point Routing

- [ ] nearest-node lookup
- [ ] A*
- [ ] edge cost
- [ ] route geometry
- [ ] route statistics
- [ ] API endpoint
- [ ] frontend route rendering

Success criterion:

```text
A → B
→ bikeability-optimized route
```

---

## Milestone 7 — Loop Generation

- [ ] candidate waypoint generation
- [ ] candidate route construction
- [ ] distance constraints
- [ ] route scoring
- [ ] candidate ranking
- [ ] loop API
- [ ] frontend UI

Success criterion:

```text
start + target distance
→ useful cycling loop
```

---

## Milestone 8 — Elevation

- [ ] elevation data provider
- [ ] elevation lookup
- [ ] grade calculation
- [ ] elevation gain
- [ ] profile-specific grade penalty

---

## Milestone 9 — Intersection Modeling

- [ ] node feature extraction
- [ ] intersection penalties
- [ ] route-level intersection metrics
- [ ] scoring integration

---

## Milestone 10 — External Traffic Data

- [ ] provider abstraction
- [ ] city-specific traffic source
- [ ] road-to-traffic matching
- [ ] traffic penalties
- [ ] cache traffic results

---

# 36. Subagent Decomposition

The project can be implemented effectively by assigning agents to isolated workstreams.

## Agent A — Backend Foundation

Own:

```text
backend/
Dockerfile
FastAPI
config
health
API structure
```

Deliverable:

```text
working FastAPI service
```

---

## Agent B — OSM / Graph Pipeline

Own:

```text
graph/
data ingestion
OSMnx
normalization
caching
```

Deliverable:

```text
load_city_graph(city)
```

with tests.

---

## Agent C — Bikeability Model

Own:

```text
scoring/
features.py
bikeability.py
profiles.py
```

Deliverable:

```text
score_graph(graph, profile)
```

with deterministic tests.

---

## Agent D — Routing

Own:

```text
routing/
A*
edge costs
route construction
route statistics
```

Deliverable:

```text
route_point_to_point(...)
```

---

## Agent E — Loop Optimization

Own:

```text
route_generation.py
candidate generation
route ranking
loop constraints
```

Deliverable:

```text
generate_loop(...)
```

Start with a heuristic implementation, not an exact optimizer.

---

## Agent F — Frontend

Own:

```text
React
TypeScript
map
controls
route UI
bikeability visualization
```

Deliverable:

```text
interactive map application
```

---

## Agent G — Integration / QA

Own:

```text
integration tests
API tests
fixture graphs
Docker Compose
end-to-end workflow
```

The integration agent should verify that the individual modules fit together rather than duplicating their implementation.

---

# 37. Agent Contracts

Agents should communicate through stable interfaces.

Example graph interface:

```python
def load_city_graph(city_id: str) -> nx.MultiDiGraph:
    ...
```

Scoring:

```python
def score_graph(
    graph: nx.MultiDiGraph,
    profile: CyclingProfile,
) -> nx.MultiDiGraph:
    ...
```

Point-to-point routing:

```python
def route_point_to_point(
    graph: nx.MultiDiGraph,
    start: Coordinate,
    end: Coordinate,
    profile: CyclingProfile,
) -> Route:
    ...
```

Loop generation:

```python
def generate_loop(
    graph: nx.MultiDiGraph,
    start: Coordinate,
    target_distance_m: float,
    profile: CyclingProfile,
) -> Route:
    ...
```

The API layer should depend on these interfaces rather than implementation details.

---

# 38. Important Algorithmic Principle

Keep these concepts separate:

```text
raw road attributes
        ↓
    features
        ↓
 bikeability score
        ↓
   routing cost
        ↓
 route optimization
```

Do not collapse everything into one function.

For example:

```text
speed = road property
bikeability = cyclist preference model
cost = algorithmic tradeoff
```

This separation makes it possible to:

- change cyclist profiles
- compare scoring models
- tune route behavior
- add machine learning later
- debug unexpected routes

---

# 39. Future: Learned Bikeability

Once the hand-designed model is useful, it can be replaced or augmented by a learned model.

Potential training data:

```text
road features
+
actual cyclist GPS traces
+
roads cyclists chose
```

Learn:

```text
P(cyclist chooses edge | edge features)
```

Then transform the model into routing cost:

```text
high probability of cyclist choice
    ↓
low cost

low probability
    ↓
high cost
```

The current architecture should make this possible without rewriting the graph or API layers.

---

# 40. Future: Personalized Routing

Eventually the scoring model can include explicit user preferences:

```text
traffic tolerance
hill tolerance
surface preference
bike infrastructure preference
distance preference
scenery preference
```

A user profile becomes a set of weights rather than a separate routing system.

Conceptually:

```python
profile = CyclingProfile(
    traffic_weight=1.5,
    grade_weight=0.5,
    infrastructure_weight=2.0,
    surface_weight=1.0,
)
```

---

# 41. Future: Scenic / Interesting Routes

Bikeability does not necessarily equal scenic quality.

A later model could add:

```text
parks
waterfront
tree cover
views
historic areas
quietness
restaurants/cafes
```

Then the objective could become:

```text
cycling quality
+
scenic quality
+
road quality
```

without changing the fundamental routing architecture.

---

# 42. MVP Definition

The MVP is complete when the following workflow works end-to-end:

```text
User opens frontend
        ↓
Selects city
        ↓
Chooses starting point
        ↓
Chooses target distance
        ↓
Chooses cyclist profile
        ↓
Clicks "Generate Route"
        ↓
FastAPI request
        ↓
Load cached OSM graph
        ↓
Score graph
        ↓
Generate candidate routes
        ↓
Rank routes
        ↓
Return GeoJSON + route metrics
        ↓
React renders route
        ↓
User can inspect route quality
        ↓
User can export GPX
```

The first version should use:

```text
OSM
+
OSMnx
+
NetworkX
+
FastAPI
+
React/TypeScript
+
MapLibre/Leaflet
+
filesystem caching
```

No database, machine learning, commercial traffic API, or complex optimization solver is required for the MVP.

---

# 43. Core Success Metric

The project should not be evaluated primarily on whether it produces the shortest route.

The key question is:

> **Does the generated route look like a route an experienced cyclist would actually want to ride?**

Validation should therefore compare generated routes against:

- known local cycling corridors
- manually selected good roads
- real cycling routes where data is available
- qualitative inspection on the map

The scoring model and loop optimizer should be tuned based on these observations.

---

# 44. Initial Target

Build the smallest version that can do:

```text
"Start here.
Give me a 30-mile road cycling loop.
Maximize high-quality roads.
Minimize high-speed/high-traffic exposure.
Return the route on a map and as GPX."
```

Once that works reliably, improve the model instead of prematurely replacing the architecture.

The core technical pipeline remains:

```text
OSM
 ↓
Graph
 ↓
Features
 ↓
Bikeability
 ↓
Routing Cost
 ↓
A*
 ↓
Loop Optimization
 ↓
GeoJSON / GPX
 ↓
React Map
```

# 10A. Extended Weighting System and Frontend/Backend Contract

## Weighting model

Treat the scoring system as a first-class, versioned domain model. Keep four layers separate:

```text
Raw OSM / external data
        ↓
Feature normalization
        ↓
Normalized feature vector [0, 1]
        ↓
Profile-specific weights
        ↓
Bikeability score [0, 10]
        ↓
Routing cost
        ↓
A* / loop optimization
```

### Normalized road features

Each routable edge should expose a normalized feature vector. Prefer quality scores in `[0, 1]` over raw penalties.

```python
@dataclass
class RoadFeatures:
    infrastructure_quality: float
    road_comfort: float
    speed_comfort: float
    traffic_comfort: float
    surface_quality: float
    grade_comfort: float

    protected_infrastructure: bool
    dedicated_bike_lane: bool
    shared_lane: bool

    highway_class: str
    traversable: bool

    # Raw values retained for diagnostics/UI.
    length_m: float
    speed_kph: float | None
    grade: float | None
    traffic_volume: float | None
```

The scoring layer should consume normalized features and should not know how an OSM tag was parsed.

### Initial six-factor model

Use this as the first implementation:

```text
Infrastructure       30%
Road comfort         20%
Speed comfort        15%
Traffic comfort      15%
Surface quality      10%
Grade comfort        10%
```

So:

```text
bikeability_0_to_1 =
    0.30 * infrastructure_quality
  + 0.20 * road_comfort
  + 0.15 * speed_comfort
  + 0.15 * traffic_comfort
  + 0.10 * surface_quality
  + 0.10 * grade_comfort

bikeability = 10 * bikeability_0_to_1
```

The weights are starting hypotheses, not ground truth. They must be external configuration, versioned, and easy to tune.

### Why normalize?

Feature normalization keeps the meaning of weights stable. A traffic weight of `0.20` means traffic matters twice as much as a feature with weight `0.10`, regardless of the raw units or number of buckets used by that feature.

The invariant should be:

```text
all feature scores ∈ [0, 1]
all weights >= 0
sum(weights) == 1
final bikeability ∈ [0, 10]
```

### Hard constraints vs soft preferences

Do not turn every undesirable road characteristic into a lower score.

```text
Hard constraint:
    bicycle=no
    motorway
    inaccessible edge
    → remove from bike graph

Soft penalty:
    high speed
    high traffic
    steep grade
    rough surface
    → lower feature quality / bikeability

Preference:
    protected infrastructure
    smooth pavement
    hills
    quiet roads
    → profile-specific weighting
```

This distinction prevents the optimizer from choosing a prohibited road just because its other characteristics happen to produce a high score.

## Feature mappings

### Infrastructure quality

Suggested starting mapping:

```text
1.00  protected cycle track / physically separated facility
0.95  dedicated bike path
0.80  high-quality bike lane
0.60  standard bike lane
0.35  shared lane / bicycle boulevard
0.15  sharrow
0.00  no bicycle infrastructure
```

Pseudocode:

```text
function infrastructure_quality(edge):
    if protected_cycle_track(edge): return 1.00
    if dedicated_path(edge):        return 0.95
    if high_quality_lane(edge):     return 0.80
    if bike_lane(edge):             return 0.60
    if shared_lane(edge):           return 0.35
    if sharrow(edge):               return 0.15
    return 0.00
```

### Road comfort

Start with road class, while avoiding double-counting bike infrastructure:

```text
living_street   → 1.00
residential     → 1.00
service         → 0.90
tertiary        → 0.70
secondary       → 0.45
primary         → 0.20
trunk           → 0.00
motorway        → excluded
```

Infrastructure should remain its own feature, so a primary road with strong protection can still score well overall.

### Speed comfort

Use a smooth function rather than discrete buckets when possible.

```python
def speed_comfort(speed_mph: float | None) -> float:
    if speed_mph is None:
        return 0.50
    if speed_mph <= 20:
        return 1.00
    if speed_mph >= 45:
        return 0.00
    return 1.0 - (speed_mph - 20) / 25
```

This should be configurable later. A nonlinear curve may better represent real rider behavior.

### Traffic comfort

When measured traffic data exists, normalize it to a quality score. A first approximation:

```text
< 1,000 vehicles/day      → 1.00
1,000–3,000                → 0.85
3,000–7,500                → 0.65
7,500–15,000               → 0.40
15,000–25,000              → 0.20
> 25,000                   → 0.00
```

Missing data must not be interpreted as low traffic. Keep it explicit:

```python
traffic_volume: float | None
traffic_confidence: float  # 0..1
```

A future provider can replace estimated traffic values without changing the scoring API.

### Surface quality

Starting values:

```text
smooth asphalt       → 1.00
good concrete        → 0.90
rough asphalt        → 0.70
paved mixed surface  → 0.60
gravel               → 0.30
dirt                 → 0.10
cobblestone          → 0.10
unknown              → 0.50
```

Profiles may weight this very differently. Road cycling should care more about smooth surfaces than a leisure/gravel profile.

### Grade comfort

Use absolute grade in the MVP:

```python
def grade_comfort(grade: float | None) -> float:
    if grade is None:
        return 0.50
    g = abs(grade)
    if g <= 0.03:
        return 1.00
    if g >= 0.12:
        return 0.00
    return 1.0 - (g - 0.03) / 0.09
```

Later, separate uphill and downhill behavior.

## Cycling profiles

Profiles change weights, not feature extraction.

Example configuration:

```yaml
version: 1

profiles:
  road:
    weights:
      infrastructure: 0.25
      road_comfort: 0.15
      speed: 0.10
      traffic: 0.15
      surface: 0.20
      grade: 0.15

  commuter:
    weights:
      infrastructure: 0.35
      road_comfort: 0.20
      speed: 0.15
      traffic: 0.20
      surface: 0.05
      grade: 0.05

  leisure:
    weights:
      infrastructure: 0.30
      road_comfort: 0.25
      speed: 0.15
      traffic: 0.15
      surface: 0.05
      grade: 0.10
```

The exact profile values are intentionally easy to change. They should be validated at application startup.

## Routing preference is separate from road scoring

Do not use `bikeability` directly as the shortest-path cost. A route can be optimized for different tradeoffs between distance and quality.

```python
@dataclass(frozen=True)
class RoutingPreferences:
    distance_weight: float
    bikeability_weight: float
```

Invariant:

```text
distance_weight + bikeability_weight == 1
```

Conceptual edge cost:

```python
def edge_cost(edge, prefs):
    discomfort = 1.0 - edge.bikeability / 10.0
    return edge.length_m * (
        prefs.distance_weight
        + prefs.bikeability_weight * discomfort
    )
```

This supports a UI slider such as:

```text
Distance  ◀──────────────▶  Bikeability
```

without changing the underlying road model.

## Route-level objective

Loop generation needs additional penalties/constraints because optimizing individual edges is not sufficient.

```python
def route_objective(route, preferences):
    return (
        preferences.bikeability_weight
        * route.average_bikeability
        + preferences.good_road_bonus * route.pct_high_quality
        - preferences.bad_road_penalty * route.pct_bad_roads
        - preferences.intersection_penalty * route.hostile_intersections
        - preferences.distance_error_penalty * route.distance_error
    )
```

Keep each component visible in the route result for debugging.

```json
{
  "score": 8.72,
  "components": {
    "averageBikeability": 8.43,
    "highQualityBonus": 0.91,
    "badRoadPenalty": 0.04,
    "intersectionPenalty": 0.12,
    "distancePenalty": 0.46
  }
}
```

## Candidate route constraints

The loop optimizer should reject candidates before ranking them when they violate explicit constraints:

```python
@dataclass
class RouteConstraints:
    min_distance_m: float
    max_distance_m: float
    max_bad_road_fraction: float | None = None
    max_high_speed_fraction: float | None = None
    max_elevation_gain_m: float | None = None
```

This is important because otherwise an optimizer can exploit the scoring function by producing a very short or otherwise unrealistic route.

---

# 10B. Frontend ↔ Backend Contract

The frontend and backend must be independently implementable. The API contract is the boundary between them.

The backend owns the domain and publishes the HTTP contract. The frontend consumes it. Neither side should depend on internal implementation details of the other.

```text
             Stable JSON/OpenAPI contract
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
   FastAPI backend              React frontend
          │                           │
   real graph/routing          mock API responses
          │                           │
          └─────────────┬─────────────┘
                        ▼
                    integration
```

## API version

All endpoints start with:

```text
/api/v1
```

Breaking changes require a new API version.

## Transport conventions

```text
JSON over HTTP
GeoJSON LineString for route geometry
latitude/longitude in request coordinates
GeoJSON coordinates always [longitude, latitude]
distances in meters
speed in km/h
grade as decimal ratio (5% = 0.05)
percentages represented as [0, 1]
```

IDs such as `routeId`, `roadId`, `jobId`, and `cityId` are opaque strings. The frontend must not infer structure from them.

---

# 10C. Shared API Types

Use matching conceptual schemas in Python and TypeScript. FastAPI/OpenAPI should eventually be the canonical generated source for transport types.

### Coordinate

Python:

```python
class Coordinate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
```

TypeScript:

```typescript
type Coordinate = {
  lat: number;
  lon: number;
};
```

### Cycling profile

Python:

```python
class CyclingProfile(str, Enum):
    ROAD = "road"
    COMMUTER = "commuter"
    LEISURE = "leisure"
```

TypeScript:

```typescript
type CyclingProfile = "road" | "commuter" | "leisure";
```

### Route preferences

```typescript
type RoutePreferences = {
  distanceWeight: number;
  bikeabilityWeight: number;
};
```

The sum must equal `1.0`.

### Route constraints

```typescript
type RouteConstraints = {
  minDistanceM?: number;
  maxDistanceM?: number;
  maxBadRoadFraction?: number;
  maxHighSpeedFraction?: number;
  maxElevationGainM?: number;
};
```

---

# 10D. Route Response Contract

Point-to-point and loop generation should share the same response shape wherever possible.

```typescript
type RouteResponse = {
  routeId: string;

  geometry: GeoJSON.LineString;

  distanceM: number;
  elevationGainM: number;

  averageBikeability: number;
  pctHighQuality: number;
  pctBadRoads: number;
  pctProtected: number;

  hostileIntersections: number;

  score: number;

  scoreBreakdown?: {
    averageBikeability: number;
    highQualityBonus: number;
    badRoadPenalty: number;
    intersectionPenalty: number;
    distancePenalty: number;
  };

  optimization?: {
    algorithmVersion: string;
    candidatesEvaluated?: number;
    candidatesRejected?: number;
  };
};
```

The frontend should never need the NetworkX graph, edge IDs, raw OSM tags, or Python objects to render a route.

---

# 10E. Point-to-Point API Contract

```http
POST /api/v1/routes/point-to-point
Content-Type: application/json
```

Request:

```json
{
  "start": {
    "lat": 47.6101,
    "lon": -122.3421
  },
  "end": {
    "lat": 47.6205,
    "lon": -122.3493
  },
  "profile": "road",
  "preferences": {
    "distanceWeight": 0.35,
    "bikeabilityWeight": 0.65
  }
}
```

Response:

```json
{
  "routeId": "rt_123",
  "geometry": {
    "type": "LineString",
    "coordinates": [
      [-122.3421, 47.6101],
      [-122.3400, 47.6120]
    ]
  },
  "distanceM": 12430,
  "elevationGainM": 112,
  "averageBikeability": 8.2,
  "pctHighQuality": 0.91,
  "pctBadRoads": 0.02,
  "pctProtected": 0.36,
  "hostileIntersections": 2,
  "score": 8.47
}
```

Backend flow:

```text
request validation
    ↓
load graph
    ↓
resolve profile + preferences
    ↓
nearest routable node(start/end)
    ↓
A*
    ↓
route metrics
    ↓
GeoJSON response
```

---

# 10F. Loop API Contract

```http
POST /api/v1/routes/loop
Content-Type: application/json
```

Request:

```json
{
  "start": {
    "lat": 47.6101,
    "lon": -122.3421
  },
  "targetDistanceM": 50000,
  "profile": "road",
  "preferences": {
    "distanceWeight": 0.20,
    "bikeabilityWeight": 0.80
  },
  "constraints": {
    "minDistanceM": 45000,
    "maxDistanceM": 55000,
    "maxBadRoadFraction": 0.05,
    "maxHighSpeedFraction": 0.02
  }
}
```

The response uses `RouteResponse`.

Backend flow:

```text
request validation
    ↓
load graph
    ↓
resolve profile
    ↓
sample candidate waypoints
    ↓
construct candidate loops using A*
    ↓
reject invalid candidates
    ↓
score candidates
    ↓
select best candidate
    ↓
return RouteResponse
```

---

# 10G. Bikeability Network API Contract

For city-wide visualization:

```http
GET /api/v1/cities/{cityId}/bikeability
```

MVP response can use GeoJSON:

```json
{
  "cityId": "seattle",
  "scoreVersion": "v1",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "bikeability": 8.4
      },
      "geometry": {
        "type": "LineString",
        "coordinates": []
      }
    }
  ]
}
```

The frontend should treat the score as data and choose how to visualize it.

For large cities, replace this endpoint's payload with vector tiles rather than returning millions of JSON coordinates.

---

# 10H. Road Inspection API

Useful for debugging the scoring model:

```http
GET /api/v1/roads/{roadId}
```

Example response:

```json
{
  "roadId": "123456:0",
  "geometry": {
    "type": "LineString",
    "coordinates": []
  },
  "features": {
    "highway": "secondary",
    "speedKph": 48,
    "lanes": 2,
    "surface": "asphalt",
    "protectedBikeInfrastructure": false,
    "bikeLane": true,
    "grade": 0.041
  },
  "bikeability": {
    "score": 6.9,
    "components": {
      "infrastructure": 0.60,
      "roadComfort": 0.45,
      "speed": 0.55,
      "traffic": 0.70,
      "surface": 1.00,
      "grade": 0.88
    }
  }
}
```

This endpoint lets developers click a road on the map and understand exactly why it received its score.

---

# 10I. Error Contract

All API errors should use one shape:

```json
{
  "error": {
    "code": "ROUTE_NOT_FOUND",
    "message": "No valid cycling route could be constructed.",
    "details": {
      "reason": "destination_unreachable"
    }
  }
}
```

Frontend behavior should switch on the stable `code`, never on the human-readable `message`.

Suggested codes:

```text
INVALID_REQUEST
INVALID_COORDINATES
CITY_NOT_AVAILABLE
ROUTE_NOT_FOUND
DISTANCE_CONSTRAINT_UNSATISFIABLE
GRAPH_UNAVAILABLE
ROUTE_GENERATION_FAILED
INTERNAL_ERROR
```

---

# 10J. OpenAPI Contract Workflow

FastAPI produces the canonical OpenAPI document:

```text
Pydantic models
      ↓
FastAPI
      ↓
/openapi.json
      ↓
TypeScript client/types
```

The frontend should eventually generate API types/client code from OpenAPI. This prevents the frontend and backend agents from independently inventing slightly different request/response shapes.

Until type generation is introduced, the frontend agent should keep hand-written types matching the schemas in this README.

---

# 10K. Frontend State Contract

Keep UI state separate from API/domain data.

```typescript
type RouteRequestState = {
  start: Coordinate | null;
  end: Coordinate | null;
  targetDistanceM: number | null;
  profile: CyclingProfile;
  preferences: RoutePreferences;
  constraints: RouteConstraints;
};
```

Recommended flow:

```text
RouteControls
      ↓
useRoute()
      ↓
API client
      ↓
RouteResponse
      ↓
Map + RouteSummary
```

The `Map` component should render data. It should not know how routing works or make domain decisions.

---

# 10L. Frontend Mocking Contract

The frontend agent must be able to work before the backend is finished.

Provide a mock API that returns a valid `RouteResponse`:

```typescript
export const mockLoopResponse: RouteResponse = {
  routeId: "mock-route",
  geometry: {
    type: "LineString",
    coordinates: [
      [-122.34, 47.61],
      [-122.35, 47.62],
      [-122.34, 47.61],
    ],
  },
  distanceM: 30200,
  elevationGainM: 420,
  averageBikeability: 8.4,
  pctHighQuality: 0.92,
  pctBadRoads: 0.02,
  pctProtected: 0.30,
  hostileIntersections: 2,
  score: 8.7,
};
```

The frontend UI should be fully functional against this mock before integration with the real FastAPI service.

---

# 10M. Subagent Contract Boundaries

Subagents should own narrow areas and communicate only through stable interfaces.

## Graph/Data Agent

Owns:

```text
backend/app/graph/*
backend/app/services/graph.py
scripts/data/*
```

Public contract:

```python
def load_city_graph(city_id: str) -> nx.MultiDiGraph:
    ...
```

## Scoring Agent

Owns:

```text
backend/app/scoring/*
backend/app/services/scoring.py
config/scoring/*
```

Public contracts:

```python
def build_features(edge) -> RoadFeatures:
    ...

def score_road(
    features: RoadFeatures,
    profile: CyclingProfile,
) -> float:
    ...

def score_graph(
    graph: nx.MultiDiGraph,
    profile: CyclingProfile,
) -> nx.MultiDiGraph:
    ...
```

## Routing Agent

Owns:

```text
backend/app/routing/*
backend/app/services/routing.py
```

Public contract:

```python
def route_point_to_point(
    graph: nx.MultiDiGraph,
    request: PointToPointRequest,
) -> Route:
    ...
```

## Optimization Agent

Owns:

```text
backend/app/optimization/*
backend/app/services/route_generation.py
```

Public contract:

```python
def generate_loop(
    graph: nx.MultiDiGraph,
    request: LoopRequest,
) -> Route:
    ...
```

## API Agent

Owns:

```text
backend/app/api/*
backend/app/models/*
```

Responsibilities:

```text
HTTP validation
request/response schemas
error contract
OpenAPI
translation between API DTOs and domain objects
```

The API agent must not implement graph algorithms.

## Frontend Agent

Owns:

```text
frontend/*
```

Responsibilities:

```text
React UI
map rendering
controls
API client
loading states
error states
route presentation
mock API
```

The frontend agent must not duplicate routing/scoring logic.

## Integration Agent

Owns:

```text
tests/integration/*
docker-compose.yml
Makefile
CI
```

Responsibilities:

```text
wire services together
run end-to-end tests
verify API contract
verify Docker workflow
```

---

# 10N. Definition of Done for Subagent Work

A subagent task is complete when it includes:

```text
implementation
+ unit tests
+ stable interface/schema
+ deterministic behavior where practical
+ documentation for non-obvious behavior
```

Cross-agent dependencies should reference interface names, not implementation details.

Example:

```text
GOOD:
    scoring agent exposes score_graph(...)
    routing agent consumes scored graph

BAD:
    routing agent reaches into scoring agent's internal helper functions
```

---

# 10O. Integration Test Contract

The first end-to-end integration test should be tiny and deterministic.

Use a hand-built graph fixture:

```text
A ───── B ───── C
│               │
└──── D ────────┘
```

Assign known edge features and known bikeability values.

Then test:

```text
fixture graph
    ↓
score
    ↓
A → C route
    ↓
FastAPI endpoint
    ↓
JSON response
    ↓
frontend mock/API client
```

This avoids needing a full city download just to verify that the layers are connected correctly.

---

# 10P. Contract Invariants Checklist

Every agent should respect these invariants:

```text
[ ] Bikeability is always 0..10.
[ ] Normalized feature values are always 0..1.
[ ] Profile weights are non-negative and sum to 1.
[ ] Route percentages are 0..1.
[ ] Distances are meters.
[ ] Speeds are km/h.
[ ] Grade is a decimal ratio.
[ ] GeoJSON coordinates are [longitude, latitude].
[ ] Illegal/inaccessible edges are removed, not merely penalized.
[ ] IDs are opaque strings.
[ ] API errors use stable error codes.
[ ] API version is /api/v1.
[ ] Frontend does not depend on NetworkX/OSMnx internals.
[ ] Scoring configuration is external and versioned.
```

---

# 10Q. Recommended Agent Execution Order

The work can proceed in parallel after the contracts are established.

```text
                     API/domain schemas
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
      Graph Agent       Scoring Agent      Frontend Agent
          │                  │                  │
          ▼                  ▼            mock API contract
      graph fixture      scoring tests           │
          │                  │                    │
          └──────────────┬───┴────────────────────┘
                         ▼
                   Routing Agent
                         │
                         ▼
                Loop Optimization Agent
                         │
                         ▼
                  API Integration
                         │
                         ▼
                   End-to-End QA
```

The key requirement is that frontend work must not wait for the real routing algorithm, and routing/scoring work must not wait for the production UI.

The stable boundary is the typed JSON/OpenAPI contract above.

