from typing import Any

from app.features.mappings import (
    grade_comfort,
    infrastructure_quality,
    road_comfort,
    speed_comfort,
    surface_quality,
    traffic_comfort,
)
from app.features.model import RoadFeatures
from app.features.normalize import (
    has_bike_lane,
    has_dedicated_bike_path,
    has_protected_infrastructure,
    has_shared_lane,
    has_sharrow,
    is_traversable,
    normalize_highway_class,
    normalize_speed_kph,
    normalize_surface,
)


def _length_m(edge_data: dict[str, Any]) -> float:
    length_m = edge_data.get("length_m", edge_data.get("length"))
    if length_m is None:
        msg = "Edge is missing length_m."
        raise ValueError(msg)
    return float(length_m)


def build_features(edge_data: dict[str, Any]) -> RoadFeatures:
    highway_class = normalize_highway_class(edge_data.get("highway"))
    speed_kph = normalize_speed_kph(edge_data.get("maxspeed"))
    surface = normalize_surface(edge_data.get("surface"))
    grade = edge_data.get("grade")
    grade_value = float(grade) if grade is not None else None
    traffic_volume = edge_data.get("traffic_volume")
    traffic_value = float(traffic_volume) if traffic_volume is not None else None
    traffic_confidence = (
        1.0
        if traffic_value is not None
        else float(edge_data.get("traffic_confidence", 0.0))
    )

    protected = has_protected_infrastructure(edge_data)
    dedicated_path = has_dedicated_bike_path(edge_data)
    bike_lane = has_bike_lane(edge_data)
    shared_lane = has_shared_lane(edge_data)
    sharrow = has_sharrow(edge_data)

    return RoadFeatures(
        infrastructure_quality=infrastructure_quality(
            protected=protected,
            dedicated_path=dedicated_path,
            bike_lane=bike_lane,
            shared_lane=shared_lane,
            sharrow=sharrow,
        ),
        road_comfort=road_comfort(highway_class),
        speed_comfort=speed_comfort(speed_kph),
        traffic_comfort=traffic_comfort(traffic_value),
        surface_quality=surface_quality(surface),
        grade_comfort=grade_comfort(grade_value),
        protected_infrastructure=protected,
        dedicated_bike_lane=bike_lane,
        shared_lane=shared_lane or sharrow,
        highway_class=highway_class,
        traversable=is_traversable(edge_data),
        length_m=_length_m(edge_data),
        speed_kph=speed_kph,
        grade=grade_value,
        traffic_volume=traffic_value,
        traffic_confidence=traffic_confidence,
    )
