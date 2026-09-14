import uuid

import networkx as nx
from app.elevation.provider import sample_path_elevations
from app.models.requests import (
    FromRoadsRequest,
    LoopRouteRequest,
    ManualRouteRequest,
    SegmentRouteRequest,
    TraceExtendRequest,
)
from app.models.responses import (
    OptimizationMetadata,
    RouteResponse,
    RouteScoreBreakdown,
    SegmentRouteResponse,
    TraceExtendResponse,
)
from app.optimization.loop import generate_loop
from app.routing.ids import make_road_id, parse_road_id
from app.routing.metrics import (
    RoadEdge,
    RouteMetrics,
    build_line_string,
    build_line_string_from_edges,
    compute_route_metrics,
    compute_route_metrics_from_edges,
)
from app.routing.point_to_point import RoutingError, route_point_to_point
from app.routing.resolve import resolve_road_edges
from app.routing.trace import extend_trace
from app.services.city_graph import get_scored_graph
from app.services.route_store import save_route


def route_segment(
    request: SegmentRouteRequest, city_id: str = "fixture"
) -> SegmentRouteResponse:
    _graph, bike_graph = get_scored_graph(city_id, request.profile.value)
    path, _metrics, geometry = route_point_to_point(
        bike_graph,
        request.start,
        request.end,
        request.preferences,
    )
    metrics = _metrics_with_elevation(bike_graph, path)
    return SegmentRouteResponse(
        geometry=geometry,
        distance_m=metrics.distance_m,
        average_bikeability=metrics.average_bikeability,
        elevation_gain_m=metrics.elevation_gain_m,
    )


def route_manual(
    request: ManualRouteRequest, city_id: str = "fixture"
) -> RouteResponse:
    _graph, bike_graph = get_scored_graph(city_id, request.profile.value)
    full_path: list[int] = []
    for start, end in zip(request.waypoints, request.waypoints[1:], strict=False):
        segment_path, _, _ = route_point_to_point(
            bike_graph,
            start,
            end,
            request.preferences,
        )
        if full_path:
            full_path.extend(segment_path[1:])
        else:
            full_path.extend(segment_path)

    metrics = _metrics_with_elevation(bike_graph, full_path)
    response = _metrics_to_route_response(
        route_id=f"rt_{uuid.uuid4().hex[:12]}",
        geometry=build_line_string(bike_graph, full_path),
        metrics=metrics,
    )
    save_route(response)
    return response


def route_from_roads(
    request: FromRoadsRequest, city_id: str = "fixture"
) -> RouteResponse:
    _graph, bike_graph = get_scored_graph(city_id, request.profile.value)
    edges = _edges_from_road_ids(bike_graph, request.road_ids)
    return _assemble_from_edges(bike_graph, edges)


def route_trace_extend(
    request: TraceExtendRequest, city_id: str = "fixture"
) -> TraceExtendResponse:
    _graph, bike_graph = get_scored_graph(city_id, request.profile.value)
    selected = (
        _edges_from_road_ids(bike_graph, request.selected_road_ids)
        if request.selected_road_ids
        else []
    )
    clicked = _clicked_orientations(bike_graph, request.clicked_road_id)
    result = extend_trace(
        bike_graph,
        selected,
        clicked,
        start=request.start,
        preferences=request.preferences,
        head_only=request.start is not None,
    )
    route = _assemble_from_edges(bike_graph, result.edges)
    return TraceExtendResponse(
        road_ids=[make_road_id(*edge) for edge in result.edges],
        action=result.action,
        route=route,
    )


def _clicked_orientations(graph: nx.MultiDiGraph, road_id: str) -> list[RoadEdge]:
    try:
        source, target, key = parse_road_id(road_id)
    except ValueError as exc:
        raise RoutingError("INVALID_REQUEST", str(exc)) from exc

    found: list[RoadEdge] = []
    seen: set[RoadEdge] = set()
    for candidate_source, candidate_target, candidate_key in (
        (source, target, key),
        (target, source, key),
    ):
        try:
            resolved = resolve_road_edges(
                graph, candidate_source, candidate_target, candidate_key
            )
        except RoutingError:
            continue
        for edge in resolved:
            if edge in seen:
                continue
            seen.add(edge)
            found.append(edge)
    if not found:
        raise RoutingError(
            "INVALID_REQUEST",
            f"Road '{road_id}' was not found.",
        )
    return found


def _edges_from_road_ids(graph: nx.MultiDiGraph, road_ids: list[str]) -> list[RoadEdge]:
    edges: list[RoadEdge] = []
    for road_id in road_ids:
        try:
            source, target, key = parse_road_id(road_id)
        except ValueError as exc:
            raise RoutingError("INVALID_REQUEST", str(exc)) from exc

        for resolved in resolve_road_edges(graph, source, target, key):
            if edges and resolved[0] != edges[-1][1]:
                raise RoutingError(
                    "INVALID_REQUEST",
                    "Selected roads do not form a connected path.",
                )
            edges.append(resolved)
    return edges


def route_loop(request: LoopRouteRequest, city_id: str = "fixture") -> RouteResponse:
    _graph, bike_graph = get_scored_graph(city_id, request.profile.value)
    result = generate_loop(
        bike_graph,
        request.start,
        request.target_distance_m,
        request.preferences,
        request.constraints,
    )
    metrics = _metrics_with_elevation(bike_graph, result.path)
    response = _metrics_to_route_response(
        route_id=f"rt_{uuid.uuid4().hex[:12]}",
        geometry=result.geometry,
        metrics=metrics,
        optimization=OptimizationMetadata(
            algorithm_version="loop-heuristic-v1",
            candidates_evaluated=result.candidates_evaluated,
            candidates_rejected=result.candidates_rejected,
        ),
    )
    save_route(response)
    return response


def _assemble_from_edges(graph, edges: list[RoadEdge]) -> RouteResponse:
    metrics = compute_route_metrics_from_edges(graph, edges)
    response = _metrics_to_route_response(
        route_id=f"rt_{uuid.uuid4().hex[:12]}",
        geometry=build_line_string_from_edges(graph, edges),
        metrics=metrics,
    )
    save_route(response)
    return response


def _metrics_with_elevation(graph, path: list[int]) -> RouteMetrics:
    elevations = sample_path_elevations(graph, path)
    return compute_route_metrics(graph, path, elevations=elevations)


def _metrics_to_route_response(
    *,
    route_id: str,
    geometry,
    metrics,
    optimization: OptimizationMetadata | None = None,
) -> RouteResponse:
    return RouteResponse(
        route_id=route_id,
        geometry=geometry,
        distance_m=metrics.distance_m,
        elevation_gain_m=metrics.elevation_gain_m,
        average_bikeability=metrics.average_bikeability,
        pct_high_quality=metrics.pct_high_quality,
        pct_bad_roads=metrics.pct_bad_roads,
        pct_protected=metrics.pct_protected,
        high_speed_exposure=metrics.high_speed_exposure,
        hostile_intersections=metrics.hostile_intersections,
        score=metrics.score,
        profile=metrics.profile,
        score_breakdown=RouteScoreBreakdown(
            average_bikeability=metrics.average_bikeability,
            high_quality_bonus=metrics.pct_high_quality,
            bad_road_penalty=metrics.pct_bad_roads,
            intersection_penalty=0.0,
            distance_penalty=0.0,
        ),
        optimization=optimization,
    )


__all__ = [
    "RoutingError",
    "route_from_roads",
    "route_loop",
    "route_manual",
    "route_segment",
    "route_trace_extend",
]
