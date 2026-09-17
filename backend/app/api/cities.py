from fastapi import APIRouter, Request
from starlette.responses import Response

from app.api.errors import ApiError
from app.models.common import ApiErrorCode
from app.models.responses import CityListResponse, CitySummary
from app.services.city_graph import (
    CityGraphUnavailableError,
    bikeability_etag,
    get_bikeability_tile_mvt,
)
from app.services.city_registry import get_city_summary, list_city_summaries

router = APIRouter()

_TILE_CACHE_CONTROL = "public, max-age=86400, must-revalidate"


@router.get("/cities", response_model=CityListResponse)
def list_cities() -> CityListResponse:
    return CityListResponse(cities=list_city_summaries())


@router.get("/cities/{cityId}", response_model=CitySummary)
def get_city(cityId: str) -> CitySummary:
    try:
        return get_city_summary(cityId)
    except KeyError:
        raise ApiError(
            code=ApiErrorCode.CITY_NOT_AVAILABLE,
            message=f"City '{cityId}' is not available.",
            status_code=404,
            details={"cityId": cityId},
        ) from None


@router.get("/cities/{cityId}/bikeability/tiles/{z}/{x}/{y}.pbf")
def get_city_bikeability_tile(
    request: Request,
    cityId: str,
    z: int,
    x: int,
    y: int,
) -> Response:
    try:
        get_city_summary(cityId)
    except KeyError:
        raise ApiError(
            code=ApiErrorCode.CITY_NOT_AVAILABLE,
            message=f"City '{cityId}' is not available.",
            status_code=404,
            details={"cityId": cityId},
        ) from None

    try:
        tile_bytes = get_bikeability_tile_mvt(cityId, z, x, y)
    except CityGraphUnavailableError as exc:
        raise ApiError(
            code=ApiErrorCode.GRAPH_UNAVAILABLE,
            message=str(exc),
            status_code=503,
            details={"cityId": cityId},
        ) from exc

    etag = bikeability_etag(cityId)
    if request.headers.get("if-none-match") == etag:
        return Response(
            status_code=304,
            headers={
                "Cache-Control": _TILE_CACHE_CONTROL,
                "ETag": etag,
            },
        )

    if tile_bytes is None:
        return Response(
            status_code=204,
            headers={
                "Cache-Control": _TILE_CACHE_CONTROL,
                "ETag": etag,
            },
        )

    return Response(
        content=tile_bytes,
        media_type="application/vnd.mapbox-vector-tile",
        headers={
            "Cache-Control": _TILE_CACHE_CONTROL,
            "ETag": etag,
        },
    )
