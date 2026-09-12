from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.api.errors import ApiError
from app.export.gpx import route_to_gpx
from app.models.common import ApiErrorCode
from app.models.requests import (
    FromRoadsRequest,
    LoopRouteRequest,
    ManualRouteRequest,
    SegmentRouteRequest,
)
from app.models.responses import RouteResponse, SegmentRouteResponse
from app.routing.point_to_point import RoutingError
from app.services.city_registry import resolve_city_id
from app.services.route_store import get_route
from app.services.routing import (
    route_from_roads,
    route_loop,
    route_manual,
    route_segment,
)

router = APIRouter()


def _routing_error(exc: RoutingError) -> ApiError:
    try:
        code = ApiErrorCode(exc.code)
    except ValueError:
        code = ApiErrorCode.ROUTE_GENERATION_FAILED
    return ApiError(
        code=code,
        message=exc.message,
        status_code=404 if exc.code == "ROUTE_NOT_FOUND" else 422,
        details={"reason": exc.code.lower()},
    )


@router.post("/routes/segment", response_model=SegmentRouteResponse)
def route_segment_endpoint(
    body: SegmentRouteRequest,
    cityId: str = Query(default="fixture"),
) -> SegmentRouteResponse:
    try:
        return route_segment(body, resolve_city_id(cityId))
    except RoutingError as exc:
        raise _routing_error(exc) from exc


@router.post("/routes/manual", response_model=RouteResponse)
def route_manual_endpoint(
    body: ManualRouteRequest,
    cityId: str = Query(default="fixture"),
) -> RouteResponse:
    try:
        return route_manual(body, resolve_city_id(cityId))
    except RoutingError as exc:
        raise _routing_error(exc) from exc


@router.post("/routes/from-roads", response_model=RouteResponse)
def route_from_roads_endpoint(
    body: FromRoadsRequest,
    cityId: str = Query(default="fixture"),
) -> RouteResponse:
    try:
        return route_from_roads(body, resolve_city_id(cityId))
    except RoutingError as exc:
        raise _routing_error(exc) from exc


@router.post("/routes/loop", response_model=RouteResponse)
def route_loop_endpoint(
    body: LoopRouteRequest,
    cityId: str = Query(default="fixture"),
) -> RouteResponse:
    try:
        return route_loop(body, resolve_city_id(cityId))
    except RoutingError as exc:
        raise _routing_error(exc) from exc


@router.get("/routes/{routeId}", response_model=RouteResponse)
def get_route_endpoint(routeId: str) -> RouteResponse:
    route = get_route(routeId)
    if route is None:
        raise ApiError(
            code=ApiErrorCode.ROUTE_NOT_FOUND,
            message="Route not found.",
            status_code=404,
            details={"routeId": routeId},
        )
    return route


@router.get("/routes/{routeId}/gpx")
def get_route_gpx(routeId: str) -> Response:
    route = get_route(routeId)
    if route is None:
        raise ApiError(
            code=ApiErrorCode.ROUTE_NOT_FOUND,
            message="Route not found.",
            status_code=404,
            details={"routeId": routeId},
        )
    content = route_to_gpx(route)
    return Response(content=content, media_type="application/gpx+xml")
