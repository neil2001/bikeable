from fastapi import APIRouter, Query

from app.api.errors import ApiError
from app.models.common import ApiErrorCode, CyclingProfile
from app.models.responses import RoadInspectionResponse
from app.services.city_graph import CityGraphUnavailableError, get_scored_graph
from app.services.city_registry import resolve_city_id
from app.services.road_inspection import inspect_road

router = APIRouter()


@router.get("/roads/{roadId}", response_model=RoadInspectionResponse)
def inspect_road_endpoint(
    roadId: str,
    cityId: str = Query(default="fixture"),
    profile: CyclingProfile = CyclingProfile.ROAD,
) -> RoadInspectionResponse:
    resolved_city = resolve_city_id(cityId)
    try:
        graph, _bike_graph = get_scored_graph(resolved_city, profile.value)
        return inspect_road(graph, roadId, profile)
    except CityGraphUnavailableError as exc:
        raise ApiError(
            code=ApiErrorCode.GRAPH_UNAVAILABLE,
            message=str(exc),
            status_code=503,
            details={"cityId": resolved_city, "roadId": roadId},
        ) from exc
    except KeyError as exc:
        raise ApiError(
            code=ApiErrorCode.INVALID_REQUEST,
            message=str(exc),
            status_code=404,
            details={"roadId": roadId},
        ) from exc
