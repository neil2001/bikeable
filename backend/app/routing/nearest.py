from __future__ import annotations

import math
from functools import lru_cache

import networkx as nx
from app.models.common import Coordinate
from pyproj import Transformer

DEFAULT_MAX_SNAP_M = 250.0


def nearest_node(
    graph: nx.MultiDiGraph,
    point: Coordinate,
    *,
    max_distance_m: float = DEFAULT_MAX_SNAP_M,
) -> int:
    node_id, distance_m = nearest_edge_snap(graph, point)
    if distance_m > max_distance_m:
        msg = (
            f"Point is {distance_m:.0f} m from the street network "
            f"(max {max_distance_m:.0f} m)."
        )
        raise ValueError(msg)
    return node_id


def nearest_edge_snap(graph: nx.MultiDiGraph, point: Coordinate) -> tuple[int, float]:
    """Return the closer endpoint of the nearest edge and the point-to-edge distance."""
    if graph.number_of_edges() == 0:
        msg = "Graph has no edges to snap against."
        raise ValueError(msg)

    px, py, uses_projected = _query_xy(graph, point)
    best_node: int | None = None
    best_distance = float("inf")

    for source, target, _key, edge_data in graph.edges(keys=True, data=True):
        distance, node_id = _distance_to_edge(
            graph,
            source,
            target,
            edge_data,
            px,
            py,
            uses_projected=uses_projected,
            point=point,
        )
        if distance < best_distance:
            best_distance = distance
            best_node = node_id

    if best_node is None:
        msg = "Graph has no edges to snap against."
        raise ValueError(msg)
    return best_node, best_distance


def _query_xy(
    graph: nx.MultiDiGraph, point: Coordinate
) -> tuple[float, float, bool]:
    if _projected_xy_are_metric(graph):
        crs = str(graph.graph.get("crs"))
        x, y = _wgs84_to_crs(crs).transform(point.lon, point.lat)
        return float(x), float(y), True
    return point.lon, point.lat, False


def _projected_xy_are_metric(graph: nx.MultiDiGraph) -> bool:
    crs = graph.graph.get("crs")
    if not crs or "4326" in str(crs) or graph.number_of_nodes() == 0:
        return False
    _node_id, node_data = next(iter(graph.nodes(data=True)))
    if "x" not in node_data or "y" not in node_data:
        return False
    if "lat" not in node_data or "lon" not in node_data:
        return True
    try:
        x, y = _wgs84_to_crs(str(crs)).transform(
            float(node_data["lon"]), float(node_data["lat"])
        )
    except Exception:
        return False
    error = math.hypot(x - float(node_data["x"]), y - float(node_data["y"]))
    return error < 50.0


@lru_cache(maxsize=32)
def _wgs84_to_crs(crs: str) -> Transformer:
    return Transformer.from_crs("EPSG:4326", crs, always_xy=True)


def _distance_to_edge(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    edge_data: dict,
    px: float,
    py: float,
    *,
    uses_projected: bool,
    point: Coordinate,
) -> tuple[float, int]:
    source_node = graph.nodes[source]
    target_node = graph.nodes[target]
    if uses_projected:
        coords = _edge_coords_xy(source_node, target_node, edge_data)
        distance = _min_segment_distance(px, py, coords)
        d_source = math.hypot(
            px - float(source_node["x"]), py - float(source_node["y"])
        )
        d_target = math.hypot(
            px - float(target_node["x"]), py - float(target_node["y"])
        )
    else:
        coords = _edge_coords_lonlat(source_node, target_node, edge_data)
        distance = _min_haversine_segment_m(point.lat, point.lon, coords)
        d_source = _haversine_m(
            point.lat,
            point.lon,
            float(source_node["lat"]),
            float(source_node["lon"]),
        )
        d_target = _haversine_m(
            point.lat,
            point.lon,
            float(target_node["lat"]),
            float(target_node["lon"]),
        )
    closer = source if d_source <= d_target else target
    return distance, closer


def _edge_coords_xy(
    source_node: dict, target_node: dict, edge_data: dict
) -> list[tuple[float, float]]:
    geom = edge_data.get("geometry")
    if geom is not None and hasattr(geom, "coords"):
        return [(float(x), float(y)) for x, y in geom.coords]
    return [
        (float(source_node["x"]), float(source_node["y"])),
        (float(target_node["x"]), float(target_node["y"])),
    ]


def _edge_coords_lonlat(
    source_node: dict, target_node: dict, edge_data: dict
) -> list[tuple[float, float]]:
    geom = edge_data.get("geometry")
    if geom is not None and hasattr(geom, "coords"):
        return [(float(x), float(y)) for x, y in geom.coords]
    return [
        (float(source_node["lon"]), float(source_node["lat"])),
        (float(target_node["lon"]), float(target_node["lat"])),
    ]


def _min_segment_distance(
    px: float, py: float, coords: list[tuple[float, float]]
) -> float:
    if len(coords) < 2:
        return float("inf")
    best = float("inf")
    for start, end in zip(coords, coords[1:], strict=False):
        best = min(
            best,
            _point_segment_distance(px, py, start[0], start[1], end[0], end[1]),
        )
    return best


def _min_haversine_segment_m(
    lat: float, lon: float, coords: list[tuple[float, float]]
) -> float:
    if len(coords) < 2:
        return float("inf")
    best = float("inf")
    for start, end in zip(coords, coords[1:], strict=False):
        best = min(
            best,
            _point_segment_haversine_m(lat, lon, start[1], start[0], end[1], end[0]),
        )
    return best


def _point_segment_distance(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _point_segment_haversine_m(
    lat: float,
    lon: float,
    a_lat: float,
    a_lon: float,
    b_lat: float,
    b_lon: float,
) -> float:
    dx = b_lon - a_lon
    dy = b_lat - a_lat
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return _haversine_m(lat, lon, a_lat, a_lon)
    t = max(0.0, min(1.0, ((lon - a_lon) * dx + (lat - a_lat) * dy) / length_sq))
    return _haversine_m(lat, lon, a_lat + t * dy, a_lon + t * dx)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))
