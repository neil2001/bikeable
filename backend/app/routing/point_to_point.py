import networkx as nx
from app.models.common import Coordinate, RoutePreferences
from app.routing.cost import apply_routing_costs
from app.routing.metrics import RouteMetrics, build_line_string, compute_route_metrics
from app.routing.nearest import nearest_node


class RoutingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def route_point_to_point(
    graph: nx.MultiDiGraph,
    start: Coordinate,
    end: Coordinate,
    preferences: RoutePreferences,
) -> tuple[list[int], RouteMetrics, object]:
    routing_graph = graph.copy()
    apply_routing_costs(routing_graph, preferences)

    try:
        start_node = nearest_node(routing_graph, start)
        end_node = nearest_node(routing_graph, end)
    except Exception as exc:
        raise RoutingError(
            "INVALID_COORDINATES",
            "Could not resolve start or end to the street network.",
        ) from exc

    try:
        path = nx.shortest_path(
            routing_graph,
            start_node,
            end_node,
            weight="routing_cost",
        )
    except nx.NetworkXNoPath as exc:
        raise RoutingError(
            "ROUTE_NOT_FOUND",
            "No valid cycling route could be constructed.",
        ) from exc

    metrics = compute_route_metrics(routing_graph, path)
    geometry = build_line_string(routing_graph, path)
    return path, metrics, geometry
