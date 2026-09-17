from app.models.common import RoutePreferences
from app.scoring.config import RoutingCostParams, cached_scoring_config

WALK_LINK_FACTOR = 8.0


def edge_routing_cost(
    length_m: float,
    bikeability: float,
    preferences: RoutePreferences,
    *,
    routing: RoutingCostParams | None = None,
    walk_link: bool = False,
) -> float:
    params = routing or cached_scoring_config().routing
    discomfort = 1.0 - bikeability / 10.0
    penalty = discomfort**params.gamma
    if bikeability < params.avoid_score:
        penalty *= params.avoid_factor
    cost = length_m * (
        preferences.distance_weight + preferences.bikeability_weight * penalty
    )
    if walk_link:
        cost *= WALK_LINK_FACTOR
    return cost


def routing_weight_fn(preferences: RoutePreferences):
    routing = cached_scoring_config().routing

    def weight(_source: int, _target: int, keyed: dict) -> float:
        return min(
            edge_routing_cost(
                float(data.get("length_m", data.get("length", 1.0))),
                float(data.get("bikeability", 5.0)),
                preferences,
                routing=routing,
                walk_link=bool(data.get("walk_link")),
            )
            for data in keyed.values()
        )

    return weight


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
            walk_link=bool(edge_data.get("walk_link")),
        )
