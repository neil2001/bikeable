from dataclasses import dataclass
from typing import TypeAlias

import networkx as nx
from app.features.apply import read_features_from_edge
from app.graph.geometry import edge_to_wgs84_coordinates
from app.models.common import GeoJSONLineString
from app.models.responses import RouteProfileSample

RoadEdge: TypeAlias = tuple[int, int, int]


@dataclass
class RouteMetrics:
    distance_m: float
    elevation_gain_m: float
    average_bikeability: float
    pct_high_quality: float
    pct_bad_roads: float
    pct_protected: float
    high_speed_exposure: float
    hostile_intersections: int
    score: float
    profile: list[RouteProfileSample]


def path_to_coordinates(
    graph: nx.MultiDiGraph,
    path: list[int],
    *,
    edge_keys: list[int] | None = None,
) -> list[list[float]]:
    if edge_keys is not None:
        return edges_to_coordinates(graph, _path_to_road_edges(path, edge_keys))
    if not path:
        return []
    if len(path) == 1:
        node = graph.nodes[path[0]]
        return [[float(node["lon"]), float(node["lat"])]]

    coordinates: list[list[float]] = []
    for index in range(len(path) - 1):
        source = path[index]
        target = path[index + 1]
        edge_data = _select_edge_data(graph, source, target)
        segment_coords = edge_to_wgs84_coordinates(graph, source, target, edge_data)
        if index == 0:
            coordinates.extend(segment_coords)
        else:
            coordinates.extend(segment_coords[1:])
    return coordinates


def edges_to_coordinates(
    graph: nx.MultiDiGraph,
    edges: list[RoadEdge],
) -> list[list[float]]:
    if not edges:
        return []
    coordinates: list[list[float]] = []
    for index, (source, target, key) in enumerate(edges):
        edge_data = _select_edge_data(graph, source, target, key=key)
        segment_coords = edge_to_wgs84_coordinates(graph, source, target, edge_data)
        if index == 0:
            coordinates.extend(segment_coords)
        else:
            coordinates.extend(segment_coords[1:])
    return coordinates


def build_line_string(
    graph: nx.MultiDiGraph,
    path: list[int],
    *,
    edge_keys: list[int] | None = None,
) -> GeoJSONLineString:
    return GeoJSONLineString(coordinates=path_to_coordinates(graph, path, edge_keys=edge_keys))


def build_line_string_from_edges(
    graph: nx.MultiDiGraph,
    edges: list[RoadEdge],
) -> GeoJSONLineString:
    return GeoJSONLineString(coordinates=edges_to_coordinates(graph, edges))


def road_edges_to_node_path(edges: list[RoadEdge]) -> list[int]:
    if not edges:
        return []
    path = [edges[0][0], edges[0][1]]
    for source, target, _key in edges[1:]:
        if source != path[-1]:
            msg = "Selected roads do not form a connected path."
            raise ValueError(msg)
        path.append(target)
    return path


def node_path_to_edges(graph: nx.MultiDiGraph, path: list[int]) -> list[RoadEdge]:
    edges: list[RoadEdge] = []
    for source, target in zip(path, path[1:], strict=False):
        keyed = graph.get_edge_data(source, target) or {}
        if not keyed:
            msg = f"No edge from {source} to {target}."
            raise ValueError(msg)
        key = min(keyed)
        edges.append((source, target, key))
    return edges


def _path_to_road_edges(path: list[int], edge_keys: list[int]) -> list[RoadEdge]:
    if len(path) < 2:
        return []
    if len(edge_keys) != len(path) - 1:
        msg = "edge_keys length must match path segments."
        raise ValueError(msg)
    return [
        (path[index], path[index + 1], edge_keys[index]) for index in range(len(edge_keys))
    ]


def compute_route_metrics(
    graph: nx.MultiDiGraph,
    path: list[int],
    *,
    elevations: list[float | None] | None = None,
    edge_keys: list[int] | None = None,
) -> RouteMetrics:
    if edge_keys is not None:
        return compute_route_metrics_from_edges(
            graph,
            _path_to_road_edges(path, edge_keys),
            elevations=elevations,
        )
    if len(path) < 2:
        return RouteMetrics(
            distance_m=0.0,
            elevation_gain_m=0.0,
            average_bikeability=0.0,
            pct_high_quality=0.0,
            pct_bad_roads=0.0,
            pct_protected=0.0,
            high_speed_exposure=0.0,
            hostile_intersections=0,
            score=0.0,
            profile=[],
        )

    total_length = 0.0
    weighted_bikeability = 0.0
    high_quality_length = 0.0
    bad_road_length = 0.0
    protected_length = 0.0
    high_speed_length = 0.0
    profile: list[RouteProfileSample] = []
    cumulative = 0.0

    start_elevation = elevations[0] if elevations else None
    start_bikeability = _node_bikeability(graph, path[0], path[1])
    profile.append(
        RouteProfileSample(
            distance_m=0.0,
            elevation_m=start_elevation,
            bikeability=start_bikeability,
        ),
    )

    for index in range(len(path) - 1):
        source = path[index]
        target = path[index + 1]
        edge_data = _select_edge_data(graph, source, target)
        features = read_features_from_edge(edge_data)
        length_m = float(edge_data.get("length_m", features.length_m))
        bikeability = float(edge_data.get("bikeability", 5.0))

        total_length += length_m
        weighted_bikeability += bikeability * length_m
        if bikeability >= 7.0:
            high_quality_length += length_m
        if bikeability < 5.0:
            bad_road_length += length_m
        if features.protected_infrastructure:
            protected_length += length_m
        if features.speed_kph is not None and features.speed_kph > 50:
            high_speed_length += length_m

        cumulative += length_m
        elevation_m = elevations[index + 1] if elevations else None
        profile.append(
            RouteProfileSample(
                distance_m=cumulative,
                elevation_m=elevation_m,
                bikeability=bikeability,
            ),
        )

    elevation_gain_m = 0.0
    if elevations:
        for idx in range(1, len(elevations)):
            if elevations[idx - 1] is not None and elevations[idx] is not None:
                delta = elevations[idx] - elevations[idx - 1]
                if delta > 0:
                    elevation_gain_m += delta

    average = weighted_bikeability / total_length if total_length else 0.0
    return RouteMetrics(
        distance_m=total_length,
        elevation_gain_m=elevation_gain_m,
        average_bikeability=average,
        pct_high_quality=high_quality_length / total_length if total_length else 0.0,
        pct_bad_roads=bad_road_length / total_length if total_length else 0.0,
        pct_protected=protected_length / total_length if total_length else 0.0,
        high_speed_exposure=high_speed_length / total_length if total_length else 0.0,
        hostile_intersections=0,
        score=average,
        profile=profile,
    )


def compute_route_metrics_from_edges(
    graph: nx.MultiDiGraph,
    edges: list[RoadEdge],
    *,
    elevations: list[float | None] | None = None,
) -> RouteMetrics:
    path = road_edges_to_node_path(edges)
    if len(path) < 2:
        return compute_route_metrics(graph, path, elevations=elevations)

    total_length = 0.0
    weighted_bikeability = 0.0
    high_quality_length = 0.0
    bad_road_length = 0.0
    protected_length = 0.0
    high_speed_length = 0.0
    profile: list[RouteProfileSample] = []
    cumulative = 0.0

    first_source, first_target, first_key = edges[0]
    start_elevation = elevations[0] if elevations else None
    start_bikeability = _node_bikeability(
        graph,
        first_source,
        first_target,
        key=first_key,
    )
    profile.append(
        RouteProfileSample(
            distance_m=0.0,
            elevation_m=start_elevation,
            bikeability=start_bikeability,
        ),
    )

    for index, (source, target, key) in enumerate(edges):
        edge_data = _select_edge_data(graph, source, target, key=key)
        features = read_features_from_edge(edge_data)
        length_m = float(edge_data.get("length_m", features.length_m))
        bikeability = float(edge_data.get("bikeability", 5.0))

        total_length += length_m
        weighted_bikeability += bikeability * length_m
        if bikeability >= 7.0:
            high_quality_length += length_m
        if bikeability < 5.0:
            bad_road_length += length_m
        if features.protected_infrastructure:
            protected_length += length_m
        if features.speed_kph is not None and features.speed_kph > 50:
            high_speed_length += length_m

        cumulative += length_m
        elevation_m = elevations[index + 1] if elevations else None
        profile.append(
            RouteProfileSample(
                distance_m=cumulative,
                elevation_m=elevation_m,
                bikeability=bikeability,
            ),
        )

    elevation_gain_m = 0.0
    if elevations:
        for idx in range(1, len(elevations)):
            if elevations[idx - 1] is not None and elevations[idx] is not None:
                delta = elevations[idx] - elevations[idx - 1]
                if delta > 0:
                    elevation_gain_m += delta

    average = weighted_bikeability / total_length if total_length else 0.0
    return RouteMetrics(
        distance_m=total_length,
        elevation_gain_m=elevation_gain_m,
        average_bikeability=average,
        pct_high_quality=high_quality_length / total_length if total_length else 0.0,
        pct_bad_roads=bad_road_length / total_length if total_length else 0.0,
        pct_protected=protected_length / total_length if total_length else 0.0,
        high_speed_exposure=high_speed_length / total_length if total_length else 0.0,
        hostile_intersections=0,
        score=average,
        profile=profile,
    )


def _node_bikeability(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    *,
    key: int | None = None,
) -> float:
    edge_data = _select_edge_data(graph, source, target, key=key)
    return float(edge_data.get("bikeability", 5.0))


def _select_edge_data(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    *,
    key: int | None = None,
) -> dict:
    edges = graph.get_edge_data(source, target)
    if not edges:
        msg = f"No edge from {source} to {target}."
        raise ValueError(msg)
    if key is not None:
        edge_data = edges.get(key)
        if edge_data is None:
            msg = f"No edge from {source} to {target} with key {key}."
            raise ValueError(msg)
        return edge_data
    _key, data = next(iter(edges.items()))
    return data
