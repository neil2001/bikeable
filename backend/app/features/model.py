from dataclasses import dataclass

INFRA_CLASSES = (
    "none",
    "sharrow",
    "shared",
    "lane",
    "designated_or_lcn",
    "separate_or_track",
    "exclusive_cycleway",
)

CONTEXT_CLASSES = ("none", "lcn", "greenway", "park")


@dataclass(frozen=True)
class RoadFeatures:
    infrastructure_quality: float
    road_comfort: float
    speed_comfort: float | None
    traffic_comfort: float
    surface_quality: float | None
    grade_comfort: float | None
    calm_geometry: float

    protected_infrastructure: bool
    dedicated_bike_lane: bool
    shared_lane: bool

    highway_class: str | None
    traversable: bool
    infra_class: str
    context_class: str
    oneway: bool
    in_park: bool
    lane_count: int | None

    length_m: float
    speed_kph: float | None
    grade: float | None
    traffic_volume: float | None
    traffic_confidence: float
    traffic_imputed: bool
