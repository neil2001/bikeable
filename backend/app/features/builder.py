from typing import Any

import networkx as nx

from app.features.context import context_class
from app.features.mappings import (
    calm_geometry,
    grade_comfort,
    infrastructure_quality,
    junction_sparsity,
    road_environment,
    speed_comfort,
    surface_quality,
    traffic_comfort,
)
from app.features.model import RoadFeatures
from app.features.normalize import (
    classify_infra,
    has_bike_lane,
    has_cycle_network,
    has_protected_infrastructure,
    has_shared_lane,
    has_sharrow,
    is_traversable,
    normalize_grade,
    normalize_highway_class,
    normalize_lane_count,
    normalize_oneway,
    normalize_speed_kph,
    normalize_surface,
)


def _length_m(edge_data: dict[str, Any]) -> float:
    length_m = edge_data.get("length_m", edge_data.get("length"))
    if length_m is None:
        msg = "Edge is missing length_m."
        raise ValueError(msg)
    return float(length_m)


def build_features(
    edge_data: dict[str, Any],
    *,
    graph: nx.MultiDiGraph | None = None,
    source: Any | None = None,
    target: Any | None = None,
) -> RoadFeatures:
    highway_class = normalize_highway_class(edge_data.get("highway"))
    speed_kph = normalize_speed_kph(edge_data.get("maxspeed"))
    surface = normalize_surface(edge_data.get("surface"))
    smoothness = normalize_surface(edge_data.get("smoothness"))
    grade_value = None
    if edge_data.get("grade") is not None:
        grade_value = normalize_grade(edge_data.get("grade"))
    elif edge_data.get("incline") is not None:
        grade_value = normalize_grade(edge_data.get("incline"))
    traffic_volume = edge_data.get("traffic_volume")
    traffic_value = float(traffic_volume) if traffic_volume is not None else None
    lane_count = normalize_lane_count(edge_data.get("lanes"))
    oneway = normalize_oneway(edge_data.get("oneway"))
    in_park = bool(edge_data.get("in_park"))
    on_lcn = has_cycle_network(edge_data)
    infra = classify_infra(edge_data)
    ctx = context_class(edge_data)

    protected = has_protected_infrastructure(edge_data)
    bike_lane = has_bike_lane(edge_data)
    shared_lane = has_shared_lane(edge_data)
    sharrow = has_sharrow(edge_data)

    comfort, confidence, imputed = traffic_comfort(
        traffic_value,
        highway_class=highway_class,
        lane_count=lane_count,
        speed_kph=speed_kph,
        oneway=oneway,
    )
    junction_factor = junction_sparsity(graph, source, target)

    return RoadFeatures(
        infrastructure_quality=infrastructure_quality(infra_class=infra),
        road_comfort=road_environment(
            highway_class,
            in_park=in_park,
            on_lcn=on_lcn,
            speed_kph=speed_kph,
            lane_count=lane_count,
        ),
        speed_comfort=speed_comfort(speed_kph),
        traffic_comfort=comfort,
        surface_quality=surface_quality(surface, smoothness),
        grade_comfort=grade_comfort(grade_value),
        calm_geometry=calm_geometry(
            highway_class=highway_class,
            lane_count=lane_count,
            oneway=oneway,
            junction_factor=junction_factor,
        ),
        protected_infrastructure=protected,
        dedicated_bike_lane=bike_lane
        or infra in {"lane", "separate_or_track", "exclusive_cycleway"},
        shared_lane=shared_lane or sharrow,
        highway_class=highway_class,
        traversable=is_traversable(edge_data),
        infra_class=infra,
        context_class=ctx,
        oneway=oneway,
        in_park=in_park,
        lane_count=lane_count,
        length_m=_length_m(edge_data),
        speed_kph=speed_kph,
        grade=grade_value,
        traffic_volume=traffic_value,
        traffic_confidence=confidence,
        traffic_imputed=imputed,
    )
