import networkx as nx

from app.features.apply import read_features_from_edge
from app.features.model import RoadFeatures
from app.scoring.config import (
    ProfileWeights,
    ScoringConfig,
    get_profile,
    load_scoring_config,
)


def clamp(value: float, lower: float = 0.0, upper: float = 10.0) -> float:
    return max(lower, min(upper, value))


def score_road(features: RoadFeatures, weights: ProfileWeights) -> float:
    quality = (
        weights.infrastructure * features.infrastructure_quality
        + weights.road_comfort * features.road_comfort
        + weights.speed * features.speed_comfort
        + weights.traffic * features.traffic_comfort
        + weights.surface * features.surface_quality
        + weights.grade * features.grade_comfort
    )
    return clamp(quality * 10.0)


def score_graph(
    graph: nx.MultiDiGraph,
    profile_id: str,
    *,
    config: ScoringConfig | None = None,
) -> nx.MultiDiGraph:
    scoring = config or load_scoring_config()
    weights = get_profile(profile_id, scoring)

    for _source, _target, _key, edge_data in graph.edges(keys=True, data=True):
        features = read_features_from_edge(edge_data)
        edge_data["bikeability"] = score_road(features, weights)

    graph.graph["score_version"] = str(scoring.version)
    graph.graph["score_profile"] = profile_id
    return graph
