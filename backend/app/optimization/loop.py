import math
import random
from dataclasses import dataclass

import networkx as nx
from app.models.common import Coordinate, RouteConstraints, RoutePreferences
from app.routing.metrics import RouteMetrics, build_line_string, compute_route_metrics
from app.routing.nearest import nearest_node
from app.routing.point_to_point import RoutingError, route_point_to_point


@dataclass
class LoopGenerationResult:
    path: list[int]
    metrics: RouteMetrics
    geometry: object
    candidates_evaluated: int
    candidates_rejected: int


def generate_loop(
    graph: nx.MultiDiGraph,
    start: Coordinate,
    target_distance_m: float,
    preferences: RoutePreferences,
    constraints: RouteConstraints | None = None,
    *,
    seed: int = 42,
) -> LoopGenerationResult:
    rng = random.Random(seed)
    constraints = constraints or RouteConstraints()
    min_distance = constraints.min_distance_m or target_distance_m * 0.9
    max_distance = constraints.max_distance_m or target_distance_m * 1.1

    try:
        start_node = nearest_node(graph, start)
    except ValueError as exc:
        raise RoutingError(
            "INVALID_COORDINATES",
            "Could not resolve start or end to the street network.",
        ) from exc
    start_lat = float(graph.nodes[start_node]["lat"])
    start_lon = float(graph.nodes[start_node]["lon"])

    radius_m = target_distance_m / (2 * math.pi)
    candidate_nodes = _sample_candidate_nodes(
        graph,
        start_lat,
        start_lon,
        radius_m,
        rng,
        count=12,
    )
    ranked = sorted(
        candidate_nodes,
        key=lambda node_id: _local_bikeability(graph, node_id),
        reverse=True,
    )[:6]

    best: LoopGenerationResult | None = None
    evaluated = 0
    rejected = 0

    for node_sequence in _candidate_sequences(start_node, ranked):
        evaluated += 1
        try:
            loop_path = _connect_sequence(graph, start, node_sequence, preferences)
        except RoutingError:
            rejected += 1
            continue
        metrics = compute_route_metrics(graph, loop_path)
        if not _route_is_valid(metrics, constraints, min_distance, max_distance):
            rejected += 1
            continue
        candidate = LoopGenerationResult(
            path=loop_path,
            metrics=metrics,
            geometry=build_line_string(graph, loop_path),
            candidates_evaluated=evaluated,
            candidates_rejected=rejected,
        )
        if best is None or _route_objective(
            metrics,
            target_distance_m,
            preferences,
        ) > _route_objective(best.metrics, target_distance_m, preferences):
            best = candidate

    for waypoint in ranked:
        if waypoint == start_node:
            continue
        evaluated += 1
        try:
            outbound_path, _, _ = route_point_to_point(
                graph,
                start,
                Coordinate(
                    lat=float(graph.nodes[waypoint]["lat"]),
                    lon=float(graph.nodes[waypoint]["lon"]),
                ),
                preferences,
            )
            inbound_path, _, _ = route_point_to_point(
                graph,
                Coordinate(
                    lat=float(graph.nodes[waypoint]["lat"]),
                    lon=float(graph.nodes[waypoint]["lon"]),
                ),
                start,
                preferences,
            )
        except RoutingError:
            rejected += 1
            continue

        loop_path = outbound_path + inbound_path[1:]
        metrics = compute_route_metrics(graph, loop_path)
        if not _route_is_valid(metrics, constraints, min_distance, max_distance):
            rejected += 1
            continue

        objective = _route_objective(metrics, target_distance_m, preferences)
        geometry = build_line_string(graph, loop_path)
        candidate = LoopGenerationResult(
            path=loop_path,
            metrics=metrics,
            geometry=geometry,
            candidates_evaluated=evaluated,
            candidates_rejected=rejected,
        )
        if best is None or objective > _route_objective(
            best.metrics,
            target_distance_m,
            preferences,
        ):
            best = candidate

    if best is None:
        raise RoutingError(
            "DISTANCE_CONSTRAINT_UNSATISFIABLE",
            "No valid loop could be generated for the requested distance.",
        )

    best.candidates_evaluated = evaluated
    best.candidates_rejected = rejected
    return best


def _candidate_sequences(start_node: int, ranked: list[int]) -> list[list[int]]:
    others = [node for node in ranked if node != start_node]
    if not others:
        return []
    sequences = [[others[0], others[1], others[2]]] if len(others) >= 3 else []
    if len(others) >= 2:
        sequences.append([others[0], others[1]])
    sequences.append(list(others))
    return sequences


def _connect_sequence(
    graph: nx.MultiDiGraph,
    start: Coordinate,
    node_sequence: list[int],
    preferences: RoutePreferences,
) -> list[int]:
    waypoints = (
        [start]
        + [
            Coordinate(
                lat=float(graph.nodes[node_id]["lat"]),
                lon=float(graph.nodes[node_id]["lon"]),
            )
            for node_id in node_sequence
        ]
        + [start]
    )
    full_path: list[int] = []
    for origin, destination in zip(waypoints, waypoints[1:], strict=False):
        segment_path, _, _ = route_point_to_point(
            graph, origin, destination, preferences
        )
        if full_path:
            full_path.extend(segment_path[1:])
        else:
            full_path.extend(segment_path)
    return full_path


def _sample_candidate_nodes(
    graph: nx.MultiDiGraph,
    start_lat: float,
    start_lon: float,
    radius_m: float,
    rng: random.Random,
    *,
    count: int,
) -> list[int]:
    nodes: list[int] = []
    for node_id, node_data in graph.nodes(data=True):
        lat = float(node_data["lat"])
        lon = float(node_data["lon"])
        distance = _approx_distance_m(start_lat, start_lon, lat, lon)
        if abs(distance - radius_m) <= radius_m * 0.5:
            nodes.append(int(node_id))

    if len(nodes) >= count:
        return rng.sample(nodes, count)

    all_nodes = [int(node_id) for node_id in graph.nodes]
    if not all_nodes:
        return []
    for node_id in all_nodes:
        if node_id not in nodes:
            nodes.append(node_id)
        if len(nodes) >= count:
            break
    return nodes


def _local_bikeability(graph: nx.MultiDiGraph, node_id: int) -> float:
    values: list[float] = []
    for _source, _target, _key, edge_data in graph.edges(node_id, keys=True, data=True):
        values.append(float(edge_data.get("bikeability", 0.0)))
    for _source, _target, _key, edge_data in graph.in_edges(
        node_id, keys=True, data=True
    ):
        values.append(float(edge_data.get("bikeability", 0.0)))
    return sum(values) / len(values) if values else 0.0


def _approx_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat_delta = (lat2 - lat1) * 111_320
    lon_delta = (lon2 - lon1) * 111_320 * math.cos(math.radians(lat1))
    return math.hypot(lat_delta, lon_delta)


def _route_is_valid(
    metrics: RouteMetrics,
    constraints: RouteConstraints,
    min_distance: float,
    max_distance: float,
) -> bool:
    if metrics.distance_m < min_distance or metrics.distance_m > max_distance:
        return False
    if (
        constraints.max_bad_road_fraction is not None
        and metrics.pct_bad_roads > constraints.max_bad_road_fraction
    ):
        return False
    if (
        constraints.max_high_speed_fraction is not None
        and metrics.high_speed_exposure > constraints.max_high_speed_fraction
    ):
        return False
    if (
        constraints.max_elevation_gain_m is not None
        and metrics.elevation_gain_m > constraints.max_elevation_gain_m
    ):
        return False
    return True


def _route_objective(
    metrics: RouteMetrics,
    target_distance_m: float,
    preferences: RoutePreferences,
) -> float:
    distance_error = abs(metrics.distance_m - target_distance_m)
    return (
        preferences.bikeability_weight * 10.0 * metrics.average_bikeability
        + preferences.bikeability_weight * 5.0 * metrics.pct_high_quality
        - preferences.distance_weight * 0.01 * distance_error
        - 8.0 * metrics.pct_bad_roads
    )
