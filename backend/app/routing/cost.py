from app.models.common import RoutePreferences
from app.scoring.config import RoutingCostParams, cached_scoring_config


def edge_routing_cost(
    length_m: float,
    bikeability: float,
    preferences: RoutePreferences,
    *,
    routing: RoutingCostParams | None = None,
) -> float:
    params = routing or cached_scoring_config().routing
    discomfort = 1.0 - bikeability / 10.0
    penalty = discomfort**params.gamma
    if bikeability < params.avoid_score:
        penalty *= params.avoid_factor
    return length_m * (
        preferences.distance_weight + preferences.bikeability_weight * penalty
    )


def apply_routing_costs(graph, preferences: RoutePreferences) -> None:
    routing = cached_scoring_config().routing
    for _source, _target, _key, edge_data in graph.edges(keys=True, data=True):
        bikeability = float(edge_data.get("bikeability", 5.0))
        length_m = float(edge_data.get("length_m", edge_data.get("length", 1.0)))
        edge_data["routing_cost"] = edge_routing_cost(
            length_m,
            bikeability,
            preferences,
            routing=routing,
        )
