"""Resolve overlay road IDs onto graph edges, including dropped skip-edges."""

from __future__ import annotations

import math

import networkx as nx
from app.routing.metrics import RoadEdge
from app.routing.point_to_point import RoutingError

_EXPAND_LENGTH_RATIO = 1.35
_EXPAND_LENGTH_SLACK_M = 200.0


def resolve_road_edges(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    key: int,
) -> list[RoadEdge]:
    try:
        return [_resolve_direct_edge(graph, source, target, key)]
    except RoutingError:
        expanded = _expand_missing_edge(graph, source, target)
        if expanded:
            return expanded
        raise


def resolve_road_edge(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    key: int,
) -> RoadEdge:
    return resolve_road_edges(graph, source, target, key)[0]


def _osmid_key(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, list):
        return tuple(value)
    return value


def _resolve_direct_edge(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    key: int,
) -> RoadEdge:
    if graph.has_edge(source, target, key):
        return source, target, key
    if graph.has_edge(target, source, key):
        return target, source, key

    forward_edges = graph.get_edge_data(source, target) or {}
    reverse_edges = graph.get_edge_data(target, source) or {}

    reference_osmid = None
    if key in forward_edges:
        reference_osmid = _osmid_key(forward_edges[key].get("osmid"))
    elif key in reverse_edges:
        reference_osmid = _osmid_key(reverse_edges[key].get("osmid"))

    if reference_osmid is not None:
        for edge_source, edge_target, candidates in (
            (source, target, forward_edges),
            (target, source, reverse_edges),
        ):
            for candidate_key, edge_data in candidates.items():
                if _osmid_key(edge_data.get("osmid")) == reference_osmid:
                    return edge_source, edge_target, candidate_key

    if len(forward_edges) == 1:
        only_key = next(iter(forward_edges))
        return source, target, only_key
    if len(reverse_edges) == 1 and not forward_edges:
        only_key = next(iter(reverse_edges))
        return target, source, only_key

    if not forward_edges and not reverse_edges:
        raise RoutingError(
            "INVALID_REQUEST",
            f"Road '{source}:{target}:{key}' was not found.",
        )

    raise RoutingError(
        "INVALID_REQUEST",
        f"Road '{source}:{target}:{key}' is ambiguous on the graph.",
    )


def _expand_missing_edge(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
) -> list[RoadEdge] | None:
    if source == target or source not in graph or target not in graph:
        return None
    try:
        nodes = nx.shortest_path(graph, source, target, weight="length_m")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
    if len(nodes) < 3:
        return None

    edges: list[RoadEdge] = []
    length_m = 0.0
    for left, right in zip(nodes, nodes[1:]):
        keyed = graph.get_edge_data(left, right) or {}
        if not keyed:
            return None
        edge_key, data = min(
            keyed.items(),
            key=lambda item: float(item[1].get("length_m", item[1].get("length", 0.0))),
        )
        length_m += float(data.get("length_m", data.get("length", 0.0)))
        edges.append((left, right, edge_key))

    straight_m = _node_distance_m(graph, source, target)
    limit_m = max(
        straight_m * _EXPAND_LENGTH_RATIO,
        straight_m + _EXPAND_LENGTH_SLACK_M,
    )
    if length_m > limit_m:
        return None
    return edges


def _node_distance_m(graph: nx.MultiDiGraph, left: int, right: int) -> float:
    left_node = graph.nodes[left]
    right_node = graph.nodes[right]
    if (
        "x" in left_node
        and "y" in left_node
        and "x" in right_node
        and "y" in right_node
    ):
        return math.hypot(
            float(right_node["x"]) - float(left_node["x"]),
            float(right_node["y"]) - float(left_node["y"]),
        )
    dlat = (float(right_node["lat"]) - float(left_node["lat"])) * 111_320
    dlon = (
        (float(right_node["lon"]) - float(left_node["lon"]))
        * 111_320
        * math.cos(
            math.radians((float(left_node["lat"]) + float(right_node["lat"])) / 2)
        )
    )
    return math.hypot(dlat, dlon)
