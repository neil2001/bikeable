from fastapi import APIRouter

from app.api.errors import ApiError, not_implemented
from app.models.common import ApiErrorCode
from app.models.requests import (
    LoopRouteRequest,
    ManualRouteRequest,
    SegmentRouteRequest,
)
from app.models.responses import RouteResponse, SegmentRouteResponse

router = APIRouter()


@router.post("/routes/segment", response_model=SegmentRouteResponse)
def route_segment(_body: SegmentRouteRequest) -> SegmentRouteResponse:
    raise not_implemented(
        ApiErrorCode.ROUTE_GENERATION_FAILED,
        "Point-to-point routing is not implemented yet.",
    )


@router.post("/routes/manual", response_model=RouteResponse)
def route_manual(_body: ManualRouteRequest) -> RouteResponse:
    raise not_implemented(
        ApiErrorCode.ROUTE_GENERATION_FAILED,
        "Manual routing is not implemented yet.",
    )


@router.post("/routes/loop", response_model=RouteResponse)
def route_loop(_body: LoopRouteRequest) -> RouteResponse:
    raise not_implemented(
        ApiErrorCode.ROUTE_GENERATION_FAILED,
        "Loop generation is not implemented yet.",
    )


@router.get("/routes/{routeId}", response_model=RouteResponse)
def get_route(routeId: str) -> RouteResponse:
    raise ApiError(
        code=ApiErrorCode.ROUTE_NOT_FOUND,
        message="Stored routes are not implemented yet.",
        status_code=501,
        details={"reason": "not_implemented", "routeId": routeId},
    )


@router.get("/routes/{routeId}/gpx")
def get_route_gpx(routeId: str) -> None:
    raise ApiError(
        code=ApiErrorCode.ROUTE_NOT_FOUND,
        message="GPX export is not implemented yet.",
        status_code=501,
        details={"reason": "not_implemented", "routeId": routeId},
    )
