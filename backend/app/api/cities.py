from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from starlette.responses import Response

from app.api.errors import ApiError
from app.models.common import ApiErrorCode
from app.models.responses import (
    BikeabilityNetworkResponse,
    CityListResponse,
    CitySummary,
)
from app.services.city_graph import (
    CityGraphUnavailableError,
    bikeability_etag,
    get_bikeability_overlay_path,
)
from app.services.city_registry import get_city_summary, list_city_summaries

router = APIRouter()


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


@router.get(
    "/cities/{cityId}/bikeability",
    response_model=None,
    responses={200: {"model": BikeabilityNetworkResponse}},
)
def get_city_bikeability(
    request: Request,
    cityId: str,
) -> FileResponse | Response:
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
        overlay_path = get_bikeability_overlay_path(cityId)
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
                "Cache-Control": "public, max-age=0, must-revalidate",
                "ETag": etag,
            },
        )

    return FileResponse(
        overlay_path,
        media_type="application/json",
        headers={
            "Cache-Control": "public, max-age=0, must-revalidate",
            "ETag": etag,
            "Content-Encoding": "gzip",
        },
    )
