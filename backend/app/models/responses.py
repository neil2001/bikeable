from app.models.common import (
    ApiModel,
    CyclingProfile,
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


class SegmentRouteResponse(ApiModel):
    geometry: GeoJSONLineString
    distance_m: float
    average_bikeability: float
    elevation_gain_m: float


class BikeabilityFeatureProperties(ApiModel):
    road_id: str
    bikeability: float


class BikeabilityFeature(ApiModel):
    type: str = "Feature"
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
    protected_bike_infrastructure: bool
    bike_lane: bool
    grade: float | None = None


class BikeabilityComponents(ApiModel):
    infrastructure: float
    road_comfort: float
    speed: float
    traffic: float
    surface: float
    grade: float


class RoadBikeabilityDetail(ApiModel):
    score: float
    components: BikeabilityComponents


class RoadInspectionResponse(ApiModel):
    road_id: str
    geometry: GeoJSONLineString
    features: RoadFeatureDiagnostics
    bikeability: RoadBikeabilityDetail
    profile: CyclingProfile
