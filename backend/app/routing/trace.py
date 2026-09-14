from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import networkx as nx
from app.models.common import Coordinate, RoutePreferences
from app.routing.cost import edge_routing_cost
from app.routing.metrics import RoadEdge
from app.routing.nearest import nearest_node
from app.routing.point_to_point import RoutingError

TraceAction = Literal["select", "same_road", "route"]

_INF = float("inf")
CostFn = Callable[[dict], float]


@dataclass(frozen=True)
class TraceExtendResult:
    edges: list[RoadEdge]
    action: TraceAction


def extend_trace(
    graph: nx.MultiDiGraph,
    selected: list[RoadEdge],
    clicked_orientations: list[RoadEdge],
    *,
    start: Coordinate | None,
    preferences: RoutePreferences,
    head_only: bool,
) -> TraceExtendResult:
    if not clicked_orientations:
        raise RoutingError("INVALID_REQUEST", "Clicked road was not found.")

    unique_clicked = _unique_edges(clicked_orientations)
    blocked = set(selected)

    if not selected:
        return _extend_from_origin(
            graph,
            unique_clicked,
            start=start,
            preferences=preferences,
            blocked=blocked,
        )

    head_edge = selected[-1]
    tail_edge = selected[0]
    head_node = head_edge[1]
    tail_node = tail_edge[0]

    ends: list[tuple[str, int, RoadEdge]] = [("append", head_node, head_edge)]
    if not head_only:
        ends.append(("prepend", tail_node, tail_edge))

    same_road_candidates: list[tuple[float, str, list[RoadEdge]]] = []
    for side, node, end_edge in ends:
        if not _same_road(graph, end_edge, unique_clicked):
            continue
        connector = _same_road_connector(
            graph,
            from_node=node,
            side=side,
            clicked=unique_clicked,
            blocked=blocked,
            reference=end_edge,
        )
        if connector is None:
            continue
        same_road_candidates.append((_edges_length(graph, connector), side, connector))

    if same_road_candidates:
        _cost, side, connector = min(same_road_candidates, key=lambda item: item[0])
        return TraceExtendResult(
            edges=_join(selected, connector, side),
            action=_action_for(connector, unique_clicked, used_same_road=True),
        )

    route_candidates: list[tuple[float, str, list[RoadEdge]]] = []
    routing_weight = _routing_weight_fn(preferences, blocked)
    routing_cost_fn = _routing_cost_fn(preferences)
    for side, node, _end_edge in ends:
        connector = _connector_via_shortest_path(
            graph,
            from_node=node,
            side=side,
            clicked=unique_clicked,
            blocked=blocked,
            weight=routing_weight,
            cost_fn=routing_cost_fn,
        )
        if connector is None:
            continue
        route_candidates.append(
            (_edges_cost(graph, connector, routing_cost_fn), side, connector)
        )

    if not route_candidates:
        raise RoutingError(
            "ROUTE_NOT_FOUND",
            "No valid cycling route could be constructed.",
        )

    _cost, side, connector = min(route_candidates, key=lambda item: item[0])
    return TraceExtendResult(
        edges=_join(selected, connector, side),
        action=_action_for(connector, unique_clicked, used_same_road=False),
    )


def _extend_from_origin(
    graph: nx.MultiDiGraph,
    clicked: list[RoadEdge],
    *,
    start: Coordinate | None,
    preferences: RoutePreferences,
    blocked: set[RoadEdge],
) -> TraceExtendResult:
    if start is None:
        return TraceExtendResult(edges=[clicked[0]], action="select")

    try:
        start_node = nearest_node(graph, start)
    except ValueError as exc:
        raise RoutingError(
            "INVALID_COORDINATES",
            "Could not resolve start or end to the street network.",
        ) from exc

    for orientation in clicked:
        source, target, _key = orientation
        if start_node == source:
            return TraceExtendResult(edges=[orientation], action="select")
        if start_node == target:
            return TraceExtendResult(edges=[orientation], action="select")

    connector = _connector_via_shortest_path(
        graph,
        from_node=start_node,
        side="append",
        clicked=clicked,
        blocked=blocked,
        weight=_routing_weight_fn(preferences, blocked),
        cost_fn=_routing_cost_fn(preferences),
    )
    if connector is None:
        raise RoutingError(
            "ROUTE_NOT_FOUND",
            "No valid cycling route could be constructed.",
        )
    return TraceExtendResult(
        edges=connector,
        action=_action_for(connector, clicked, used_same_road=False),
    )


def _same_road_connector(
    graph: nx.MultiDiGraph,
    *,
    from_node: int,
    side: str,
    clicked: list[RoadEdge],
    blocked: set[RoadEdge],
    reference: RoadEdge,
) -> list[RoadEdge] | None:
    subgraph = _same_road_subgraph(graph, reference, blocked)
    for source, target, key in clicked:
        if not subgraph.has_edge(source, target, key) and graph.has_edge(
            source, target, key
        ):
            subgraph.add_node(source, **graph.nodes[source])
            subgraph.add_node(target, **graph.nodes[target])
            subgraph.add_edge(source, target, key, **graph.edges[source, target, key])
    if subgraph.number_of_edges() == 0:
        return None

    def length_cost(data: dict) -> float:
        return _length_m(data)

    return _connector_via_shortest_path(
        subgraph,
        from_node=from_node,
        side=side,
        clicked=clicked,
        blocked=blocked,
        weight=_length_weight_fn(blocked),
        cost_fn=length_cost,
    )


def _connector_via_shortest_path(
    graph: nx.MultiDiGraph,
    *,
    from_node: int,
    side: str,
    clicked: list[RoadEdge],
    blocked: set[RoadEdge],
    weight,
    cost_fn: CostFn,
) -> list[RoadEdge] | None:
    best: list[RoadEdge] | None = None
    best_cost = _INF
    for orientation in clicked:
        source, target, _key = orientation
        if side == "append":
            entry = source
            if from_node == entry:
                candidate = [orientation]
            else:
                try:
                    nodes = nx.shortest_path(graph, from_node, entry, weight=weight)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                prefix = _nodes_to_edges(graph, nodes, cost_fn=cost_fn, blocked=blocked)
                if prefix[-1:] == [orientation]:
                    candidate = prefix
                else:
                    candidate = prefix + [orientation]
        else:
            exit_node = target
            if from_node == exit_node:
                candidate = [orientation]
            else:
                try:
                    nodes = nx.shortest_path(graph, exit_node, from_node, weight=weight)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                suffix = _nodes_to_edges(graph, nodes, cost_fn=cost_fn, blocked=blocked)
                candidate = [orientation] + suffix
        if _has_blocked(candidate, blocked):
            continue
        cost = sum(cost_fn(graph.edges[edge]) for edge in candidate)
        if cost < best_cost:
            best = candidate
            best_cost = cost
    return best


def _same_road_subgraph(
    graph: nx.MultiDiGraph,
    reference: RoadEdge,
    blocked: set[RoadEdge],
) -> nx.MultiDiGraph:
    reference_data = graph.edges[reference]
    subgraph = nx.MultiDiGraph()
    subgraph.graph.update(graph.graph)
    for source, target, key, data in graph.edges(keys=True, data=True):
        edge = (source, target, key)
        if edge in blocked:
            continue
        if not _identities_match(reference_data, data):
            continue
        if source not in subgraph:
            subgraph.add_node(source, **graph.nodes[source])
        if target not in subgraph:
            subgraph.add_node(target, **graph.nodes[target])
        subgraph.add_edge(source, target, key, **data)
    return subgraph


def _same_road(
    graph: nx.MultiDiGraph,
    end_edge: RoadEdge,
    clicked: list[RoadEdge],
) -> bool:
    end_data = graph.edges[end_edge]
    return any(_identities_match(end_data, graph.edges[edge]) for edge in clicked)


def _identities_match(left: dict, right: dict) -> bool:
    left_names = _names(left.get("name"))
    right_names = _names(right.get("name"))
    if left_names and right_names:
        return bool(left_names & right_names)
    left_osmid = _osmid_key(left.get("osmid"))
    right_osmid = _osmid_key(right.get("osmid"))
    return left_osmid is not None and left_osmid == right_osmid


def _names(value: object) -> set[str]:
    if value is None:
        return set()
    items = value if isinstance(value, (list, tuple, set)) else [value]
    names: set[str] = set()
    for item in items:
        text = str(item).strip().lower()
        if text:
            names.add(text)
    return names


def _osmid_key(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, list):
        return tuple(value)
    return value


def _nodes_to_edges(
    graph: nx.MultiDiGraph,
    nodes: list[int],
    *,
    cost_fn: CostFn,
    blocked: set[RoadEdge],
) -> list[RoadEdge]:
    edges: list[RoadEdge] = []
    for source, target in zip(nodes, nodes[1:], strict=False):
        keyed = graph.get_edge_data(source, target) or {}
        best_key = None
        best_cost = _INF
        for key, data in keyed.items():
            edge = (source, target, key)
            if edge in blocked:
                continue
            cost = cost_fn(data)
            if cost < best_cost:
                best_cost = cost
                best_key = key
        if best_key is None:
            raise RoutingError(
                "ROUTE_NOT_FOUND",
                "No valid cycling route could be constructed.",
            )
        edges.append((source, target, best_key))
    return edges


def _routing_cost_fn(preferences: RoutePreferences) -> CostFn:
    def cost(data: dict) -> float:
        return edge_routing_cost(
            _length_m(data),
            float(data.get("bikeability", 5.0)),
            preferences,
            walk_link=bool(data.get("walk_link")),
        )

    return cost


def _routing_weight_fn(preferences: RoutePreferences, blocked: set[RoadEdge]):
    cost_fn = _routing_cost_fn(preferences)

    def weight(source: int, target: int, keyed: dict) -> float:
        best = _INF
        for key, data in keyed.items():
            if (source, target, key) in blocked:
                continue
            best = min(best, cost_fn(data))
        return best

    return weight


def _length_weight_fn(blocked: set[RoadEdge]):
    def weight(source: int, target: int, keyed: dict) -> float:
        best = _INF
        for key, data in keyed.items():
            if (source, target, key) in blocked:
                continue
            best = min(best, _length_m(data))
        return best

    return weight


def _length_m(data: dict) -> float:
    return float(data.get("length_m", data.get("length", 1.0)))


def _edges_length(graph: nx.MultiDiGraph, edges: list[RoadEdge]) -> float:
    return sum(_length_m(graph.edges[edge]) for edge in edges)


def _edges_cost(
    graph: nx.MultiDiGraph, edges: list[RoadEdge], cost_fn: CostFn
) -> float:
    return sum(cost_fn(graph.edges[edge]) for edge in edges)


def _join(
    selected: list[RoadEdge], connector: list[RoadEdge], side: str
) -> list[RoadEdge]:
    if side == "prepend":
        return [*connector, *selected]
    return [*selected, *connector]


def _action_for(
    connector: list[RoadEdge],
    clicked: list[RoadEdge],
    *,
    used_same_road: bool,
) -> TraceAction:
    clicked_set = set(clicked)
    extra = [edge for edge in connector if edge not in clicked_set]
    if not extra:
        return "select"
    return "same_road" if used_same_road else "route"


def _unique_edges(edges: list[RoadEdge]) -> list[RoadEdge]:
    seen: set[RoadEdge] = set()
    ordered: list[RoadEdge] = []
    for edge in edges:
        if edge in seen:
            continue
        seen.add(edge)
        ordered.append(edge)
    return ordered


def _has_blocked(edges: list[RoadEdge], blocked: set[RoadEdge]) -> bool:
    return any(edge in blocked for edge in edges)
