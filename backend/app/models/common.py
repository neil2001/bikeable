from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class ApiErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_COORDINATES = "INVALID_COORDINATES"
    CITY_NOT_AVAILABLE = "CITY_NOT_AVAILABLE"
    ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"
    DISTANCE_CONSTRAINT_UNSATISFIABLE = "DISTANCE_CONSTRAINT_UNSATISFIABLE"
    GRAPH_UNAVAILABLE = "GRAPH_UNAVAILABLE"
    ROUTE_GENERATION_FAILED = "ROUTE_GENERATION_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ApiErrorBody(ApiModel):
    code: ApiErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiErrorEnvelope(ApiModel):
    error: ApiErrorBody


class Coordinate(ApiModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class CyclingProfile(StrEnum):
    ROAD = "road"
    COMMUTER = "commuter"
    LEISURE = "leisure"


class RoutePreferences(ApiModel):
    distance_weight: float = Field(ge=0, le=1)
    bikeability_weight: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def weights_must_sum_to_one(self) -> "RoutePreferences":
        total = self.distance_weight + self.bikeability_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError("distanceWeight + bikeabilityWeight must equal 1")
        return self


class RouteConstraints(ApiModel):
    min_distance_m: float | None = Field(default=None, ge=0)
    max_distance_m: float | None = Field(default=None, ge=0)
    max_bad_road_fraction: float | None = Field(default=None, ge=0, le=1)
    max_high_speed_fraction: float | None = Field(default=None, ge=0, le=1)
    max_elevation_gain_m: float | None = Field(default=None, ge=0)


class GeoJSONLineString(ApiModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]]
