from fastapi import APIRouter, Query

from app.api.errors import ApiError
from app.models.common import ApiErrorCode, CyclingProfile
from app.models.responses import RoadInspectionResponse

router = APIRouter()


@router.get("/roads/{roadId}", response_model=RoadInspectionResponse)
def inspect_road(
    roadId: str,
    cityId: str = Query(),
    profile: CyclingProfile = CyclingProfile.ROAD,
) -> RoadInspectionResponse:
    if cityId != "vancouver":
        raise ApiError(
            code=ApiErrorCode.CITY_NOT_AVAILABLE,
            message=f"City '{cityId}' is not available.",
            status_code=404,
            details={"cityId": cityId},
        )
    raise ApiError(
        code=ApiErrorCode.GRAPH_UNAVAILABLE,
        message="Road inspection requires a processed city graph.",
        status_code=501,
        details={"reason": "not_implemented", "roadId": roadId, "profile": profile},
    )
