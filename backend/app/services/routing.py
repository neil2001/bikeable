import uuid

from app.elevation.null_provider import sample_elevations
from app.models.requests import (
    LoopRouteRequest,
    ManualRouteRequest,
    SegmentRouteRequest,
)
from app.models.responses import (
    OptimizationMetadata,
    RouteResponse,
    RouteScoreBreakdown,
    SegmentRouteResponse,
)
from app.optimization.loop import generate_loop
from app.routing.point_to_point import RoutingError, route_point_to_point
from app.services.city_graph import get_scored_graph
from app.services.route_store import save_route


def route_segment(
    request: SegmentRouteRequest, city_id: str = "fixture"
) -> SegmentRouteResponse:
    _graph, bike_graph = get_scored_graph(city_id, request.profile.value)
    _path, metrics, geometry = route_point_to_point(
        bike_graph,
        request.start,
        request.end,
        request.preferences,
    )
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

    elevations = sample_elevations(len(full_path))
    from app.routing.metrics import build_line_string, compute_route_metrics

    metrics = compute_route_metrics(bike_graph, full_path, elevations=elevations)
    response = _metrics_to_route_response(
        route_id=f"rt_{uuid.uuid4().hex[:12]}",
        geometry=build_line_string(bike_graph, full_path),
        metrics=metrics,
    )
    save_route(response)
    return response


def route_loop(request: LoopRouteRequest, city_id: str = "fixture") -> RouteResponse:
    _graph, bike_graph = get_scored_graph(city_id, request.profile.value)
    result = generate_loop(
        bike_graph,
        request.start,
        request.target_distance_m,
        request.preferences,
        request.constraints,
    )
    response = _metrics_to_route_response(
        route_id=f"rt_{uuid.uuid4().hex[:12]}",
        geometry=result.geometry,
        metrics=result.metrics,
        optimization=OptimizationMetadata(
            algorithm_version="loop-heuristic-v1",
            candidates_evaluated=result.candidates_evaluated,
            candidates_rejected=result.candidates_rejected,
        ),
    )
    save_route(response)
    return response


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


__all__ = ["RoutingError", "route_loop", "route_manual", "route_segment"]
