from pydantic import Field

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
