from typing import Any

import networkx as nx

from app.features.builder import build_features
from app.features.model import RoadFeatures
from app.features.normalize import normalize_lane_count

FEATURE_PREFIX = "feat_"


def feature_key(name: str) -> str:
    return f"{FEATURE_PREFIX}{name}"


def write_features_to_edge(edge_data: dict[str, Any], features: RoadFeatures) -> None:
    edge_data[feature_key("infrastructure_quality")] = features.infrastructure_quality
    edge_data[feature_key("road_comfort")] = features.road_comfort
    edge_data[feature_key("speed_comfort")] = features.speed_comfort
    edge_data[feature_key("traffic_comfort")] = features.traffic_comfort
    edge_data[feature_key("surface_quality")] = features.surface_quality
    edge_data[feature_key("grade_comfort")] = features.grade_comfort
    edge_data[feature_key("protected_infrastructure")] = (
        features.protected_infrastructure
    )
    edge_data[feature_key("dedicated_bike_lane")] = features.dedicated_bike_lane
    edge_data[feature_key("shared_lane")] = features.shared_lane
    edge_data[feature_key("highway_class")] = features.highway_class or ""
    edge_data[feature_key("traversable")] = features.traversable
    edge_data[feature_key("length_m")] = features.length_m
    edge_data[feature_key("speed_kph")] = features.speed_kph
    edge_data[feature_key("grade")] = features.grade
    edge_data[feature_key("traffic_volume")] = features.traffic_volume
    edge_data[feature_key("traffic_confidence")] = features.traffic_confidence
    edge_data[feature_key("lane_count")] = normalize_lane_count(edge_data.get("lanes"))


def read_features_from_edge(edge_data: dict[str, Any]) -> RoadFeatures:
    if feature_key("infrastructure_quality") not in edge_data:
        return build_features(edge_data)

    return RoadFeatures(
        infrastructure_quality=float(edge_data[feature_key("infrastructure_quality")]),
        road_comfort=float(edge_data[feature_key("road_comfort")]),
        speed_comfort=float(edge_data[feature_key("speed_comfort")]),
        traffic_comfort=float(edge_data[feature_key("traffic_comfort")]),
        surface_quality=float(edge_data[feature_key("surface_quality")]),
        grade_comfort=float(edge_data[feature_key("grade_comfort")]),
        protected_infrastructure=bool(
            edge_data[feature_key("protected_infrastructure")]
        ),
        dedicated_bike_lane=bool(edge_data[feature_key("dedicated_bike_lane")]),
        shared_lane=bool(edge_data[feature_key("shared_lane")]),
        highway_class=edge_data.get(feature_key("highway_class")) or None,
        traversable=bool(edge_data[feature_key("traversable")]),
        length_m=float(edge_data[feature_key("length_m")]),
        speed_kph=_optional_float(edge_data.get(feature_key("speed_kph"))),
        grade=_optional_float(edge_data.get(feature_key("grade"))),
        traffic_volume=_optional_float(edge_data.get(feature_key("traffic_volume"))),
        traffic_confidence=float(edge_data[feature_key("traffic_confidence")]),
    )


def _optional_float(value: Any) -> float | None:
    if value in (None, "", "None"):
        return None
    return float(value)


def apply_features_to_graph(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    for _source, _target, _key, edge_data in graph.edges(keys=True, data=True):
        features = build_features(edge_data)
        write_features_to_edge(edge_data, features)
    return graph
