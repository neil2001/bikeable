from fastapi import APIRouter

from app.api.errors import ApiError
from app.models.common import ApiErrorCode, CyclingProfile
from app.models.responses import (
    BBox,
    BikeabilityNetworkResponse,
    CityListResponse,
    CitySummary,
)

router = APIRouter()

VANCOUVER = CitySummary(
    city_id="vancouver",
    name="Vancouver, BC",
    bbox=BBox(
        min_lon=-123.27,
        min_lat=49.198,
        max_lon=-123.023,
        max_lat=49.317,
    ),
    graph_version="unbuilt",
    score_version="v1",
)

CITIES = {VANCOUVER.city_id: VANCOUVER}


@router.get("/cities", response_model=CityListResponse)
def list_cities() -> CityListResponse:
    return CityListResponse(cities=list(CITIES.values()))


@router.get("/cities/{cityId}", response_model=CitySummary)
def get_city(cityId: str) -> CitySummary:
    city = CITIES.get(cityId)
    if city is None:
        raise ApiError(
            code=ApiErrorCode.CITY_NOT_AVAILABLE,
            message=f"City '{cityId}' is not available.",
            status_code=404,
            details={"cityId": cityId},
        )
    return city


@router.get(
    "/cities/{cityId}/bikeability",
    response_model=BikeabilityNetworkResponse,
)
def get_city_bikeability(
    cityId: str,
    profile: CyclingProfile = CyclingProfile.ROAD,
) -> BikeabilityNetworkResponse:
    if cityId not in CITIES:
        raise ApiError(
            code=ApiErrorCode.CITY_NOT_AVAILABLE,
            message=f"City '{cityId}' is not available.",
            status_code=404,
            details={"cityId": cityId},
        )
    raise ApiError(
        code=ApiErrorCode.GRAPH_UNAVAILABLE,
        message=(
            "Bikeability network is not available until the graph pipeline "
            "is implemented."
        ),
        status_code=501,
        details={"reason": "not_implemented", "profile": profile},
    )
