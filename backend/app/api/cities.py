from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.errors import ApiError
from app.models.common import ApiErrorCode, CyclingProfile
from app.models.responses import (
    BikeabilityNetworkResponse,
    CityListResponse,
    CitySummary,
)
from app.services.city_graph import (
    CityGraphUnavailableError,
    bikeability_etag,
    get_bikeability_overlay,
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
    response_model=BikeabilityNetworkResponse,
)
def get_city_bikeability(
    request: Request,
    cityId: str,
    profile: CyclingProfile = CyclingProfile.ROAD,
) -> BikeabilityNetworkResponse | JSONResponse:
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
        overlay = get_bikeability_overlay(cityId, profile.value)
    except CityGraphUnavailableError as exc:
        raise ApiError(
            code=ApiErrorCode.GRAPH_UNAVAILABLE,
            message=str(exc),
            status_code=503,
            details={"cityId": cityId, "profile": profile.value},
        ) from exc

    etag = bikeability_etag(cityId, profile.value)
    if request.headers.get("if-none-match") == etag:
        return JSONResponse(
            status_code=304,
            headers={
                "Cache-Control": "public, max-age=86400",
                "ETag": etag,
            },
        )

    return JSONResponse(
        content=overlay.model_dump(by_alias=True),
        headers={
            "Cache-Control": "public, max-age=86400",
            "ETag": etag,
        },
    )
