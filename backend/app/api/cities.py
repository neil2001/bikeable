from fastapi import APIRouter

from app.api.errors import ApiError
from app.models.common import ApiErrorCode, CyclingProfile
from app.models.responses import (
    BikeabilityNetworkResponse,
    CityListResponse,
    CitySummary,
)
from app.services.bikeability_map import graph_to_bikeability_response
from app.services.city_graph import CityGraphUnavailableError, get_scored_graph
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
    cityId: str,
    profile: CyclingProfile = CyclingProfile.ROAD,
) -> BikeabilityNetworkResponse:
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
        graph, _bike_graph = get_scored_graph(cityId, profile.value)
    except CityGraphUnavailableError as exc:
        raise ApiError(
            code=ApiErrorCode.GRAPH_UNAVAILABLE,
            message=str(exc),
            status_code=503,
            details={"cityId": cityId, "profile": profile.value},
        ) from exc

    return graph_to_bikeability_response(
        graph,
        city_id=cityId,
        score_version=str(graph.graph.get("score_version", "v1")),
    )
