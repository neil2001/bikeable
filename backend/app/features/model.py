from dataclasses import dataclass


@dataclass(frozen=True)
class RoadFeatures:
    infrastructure_quality: float
    road_comfort: float
    speed_comfort: float
    traffic_comfort: float
    surface_quality: float
    grade_comfort: float

    protected_infrastructure: bool
    dedicated_bike_lane: bool
    shared_lane: bool

    highway_class: str | None
    traversable: bool

    length_m: float
    speed_kph: float | None
    grade: float | None
    traffic_volume: float | None
    traffic_confidence: float
