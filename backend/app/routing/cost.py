from app.models.common import RoutePreferences


def edge_routing_cost(
    length_m: float, bikeability: float, preferences: RoutePreferences
) -> float:
    discomfort = 1.0 - bikeability / 10.0
    return length_m * (
        preferences.distance_weight + preferences.bikeability_weight * discomfort
    )


def apply_routing_costs(graph, preferences: RoutePreferences) -> None:
    for _source, _target, _key, edge_data in graph.edges(keys=True, data=True):
        bikeability = float(edge_data.get("bikeability", 5.0))
        length_m = float(edge_data.get("length_m", edge_data.get("length", 1.0)))
        edge_data["routing_cost"] = edge_routing_cost(
            length_m, bikeability, preferences
        )
