from typing import Literal

from pydantic import field_validator

from app.features.normalize import format_tag
from app.models.common import (
    ApiModel,
    GeoJSONLineString,
)


class HealthResponse(ApiModel):
    status: str = "ok"


class BBox(ApiModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


class CitySummary(ApiModel):
    city_id: str
    name: str
    bbox: BBox
    graph_version: str
    score_version: str


class CityListResponse(ApiModel):
    cities: list[CitySummary]


class RouteProfileSample(ApiModel):
    distance_m: float
    elevation_m: float | None = None
    bikeability: float


class RouteScoreBreakdown(ApiModel):
    average_bikeability: float
    high_quality_bonus: float
    bad_road_penalty: float
    intersection_penalty: float
    distance_penalty: float


class OptimizationMetadata(ApiModel):
    algorithm_version: str
    candidates_evaluated: int | None = None
    candidates_rejected: int | None = None


class RouteResponse(ApiModel):
    route_id: str
    geometry: GeoJSONLineString
    distance_m: float
    elevation_gain_m: float
    average_bikeability: float
    pct_high_quality: float
    pct_bad_roads: float
    pct_protected: float
    high_speed_exposure: float
    hostile_intersections: int
    score: float
    profile: list[RouteProfileSample]
    score_breakdown: RouteScoreBreakdown | None = None
    optimization: OptimizationMetadata | None = None
    road_ids: list[str] | None = None


class SegmentRouteResponse(ApiModel):
    geometry: GeoJSONLineString
    distance_m: float
    average_bikeability: float
    elevation_gain_m: float


class TraceExtendResponse(ApiModel):
    road_ids: list[str]
    action: Literal["select", "same_road", "route"]
    route: RouteResponse
    destination_name: str | None = None


class BikeabilityFeatureProperties(ApiModel):
    road_id: str
    bikeability: float
    osmid: int | list[int] | None = None


class BikeabilityFeature(ApiModel):
    type: str = "Feature"
    id: int | None = None
    properties: BikeabilityFeatureProperties
    geometry: GeoJSONLineString


class BikeabilityNetworkResponse(ApiModel):
    city_id: str
    score_version: str
    features: list[BikeabilityFeature]


class RoadFeatureDiagnostics(ApiModel):
    highway: str | None = None
    speed_kph: float | None = None
    lanes: int | None = None
    surface: str | None = None
    name: str | None = None
    osmid: int | list[int] | None = None
    protected_bike_infrastructure: bool
    bike_lane: bool
    grade: float | None = None

    @field_validator("highway", "surface", "name", mode="before")
    @classmethod
    def _format_string_tags(cls, value: object) -> str | None:
        return format_tag(value)


class BikeabilityComponents(ApiModel):
    infrastructure: float
    road_comfort: float
    environment: float
    speed: float | None = None
    traffic: float
    surface: float | None = None
    grade: float | None = None
    context: float = 0.0
    calm_geometry: float = 0.0


class RoadBikeabilityDetail(ApiModel):
    score: float
    components: BikeabilityComponents
    reasons: list[str] = []


class RoadInspectionResponse(ApiModel):
    road_id: str
    geometry: GeoJSONLineString
    features: RoadFeatureDiagnostics
    bikeability: RoadBikeabilityDetail
