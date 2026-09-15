from pydantic import Field, model_validator

from app.models.common import (
    ApiModel,
    Coordinate,
    CyclingProfile,
    RouteConstraints,
    RoutePreferences,
)


class SegmentRouteRequest(ApiModel):
    start: Coordinate
    end: Coordinate
    profile: CyclingProfile
    preferences: RoutePreferences
    constraints: RouteConstraints | None = None


class ManualRouteRequest(ApiModel):
    waypoints: list[Coordinate] = Field(min_length=2)
    profile: CyclingProfile
    preferences: RoutePreferences
    constraints: RouteConstraints | None = None


class LoopRouteRequest(ApiModel):
    start: Coordinate
    target_distance_m: float = Field(gt=0)
    profile: CyclingProfile
    preferences: RoutePreferences
    constraints: RouteConstraints | None = None


class FromRoadsRequest(ApiModel):
    road_ids: list[str] = Field(min_length=1)
    profile: CyclingProfile


class TraceExtendRequest(ApiModel):
    selected_road_ids: list[str] = Field(default_factory=list)
    clicked_road_id: str | None = None
    clicked: Coordinate | None = None
    start: Coordinate | None = None
    profile: CyclingProfile
    preferences: RoutePreferences

    @model_validator(mode="after")
    def require_click_target(self) -> "TraceExtendRequest":
        if not self.clicked_road_id and self.clicked is None:
            raise ValueError("clickedRoadId or clicked is required")
        return self
