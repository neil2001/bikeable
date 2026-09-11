"""Join overlapping OSMnx section extracts into one metro graph."""

from __future__ import annotations

import math
from typing import Any

import networkx as nx

from app.graph.ingest import _osmid_key


def stitch_graphs(
    graphs: list[nx.MultiDiGraph],
    *,
    snap_tolerance_m: float = 5.0,
) -> nx.MultiDiGraph:
    """Compose section graphs, dedupe overlap edges, and snap clipped endpoints."""
    if not graphs:
        msg = "At least one graph is required to stitch."
        raise ValueError(msg)

    if len(graphs) == 1:
        graph = _dedupe_overlap_edges(graphs[0].copy())
    else:
        graph = _dedupe_overlap_edges(nx.compose_all(graphs))

    snapped = _snap_endpoints(graph, snap_tolerance_m)
    return _simplify_degree_two_same_osmid(snapped)


def _dedupe_overlap_edges(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Collapse parallel edges that share the same (u, v, osmid)."""
    grouped: dict[tuple[int, int, object], list[tuple[int, dict[str, Any]]]] = {}
    for source, target, key, data in graph.edges(keys=True, data=True):
        osmid = _osmid_key(data.get("osmid"))
        grouped.setdefault((source, target, osmid), []).append((key, data))

    result = graph.copy()
    for (source, target, osmid), edges in grouped.items():
        if len(edges) <= 1:
            continue
        keeper_key, keeper_data = edges[0]
        for _key, edge_data in edges[1:]:
            for tag, value in edge_data.items():
                if keeper_data.get(tag) in (None, "") and value not in (None, ""):
                    keeper_data[tag] = value
            if result.has_edge(source, target, _key):
                result.remove_edge(source, target, _key)
        result[source][target][keeper_key].update(keeper_data)
    return result


def _undirected_degree(graph: nx.MultiDiGraph, node: int) -> int:
    return graph.degree(node)


def _leaf_nodes(graph: nx.MultiDiGraph) -> list[int]:
    return [node for node in graph.nodes if _undirected_degree(graph, node) == 1]


def _incident_edge(
    graph: nx.MultiDiGraph,
    node: int,
) -> tuple[int, int, int, dict[str, Any]]:
    for source, target, key, data in graph.edges(node, keys=True, data=True):
        return source, target, key, data
    for source, target, key, data in graph.in_edges(node, keys=True, data=True):
        return source, target, key, data
    msg = f"Leaf node {node} has no incident edges."
    raise ValueError(msg)


def _node_distance_m(graph: nx.MultiDiGraph, left: int, right: int) -> float:
    left_node = graph.nodes[left]
    right_node = graph.nodes[right]
    return math.hypot(
        float(right_node["x"]) - float(left_node["x"]),
        float(right_node["y"]) - float(left_node["y"]),
    )


def _edge_bearing(graph: nx.MultiDiGraph, source: int, target: int) -> float:
    source_node = graph.nodes[source]
    target_node = graph.nodes[target]
    return math.atan2(
        float(target_node["y"]) - float(source_node["y"]),
        float(target_node["x"]) - float(source_node["x"]),
    )


def _heading_compatible(left: float, right: float, tolerance_rad: float = math.pi / 4) -> bool:
    delta = abs(left - right) % (2 * math.pi)
    delta = min(delta, 2 * math.pi - delta)
    return delta <= tolerance_rad


def _candidate_nodes(
    graph: nx.MultiDiGraph,
    leaf: int,
    *,
    snap_tolerance_m: float,
) -> list[tuple[int, float]]:
    candidates: list[tuple[int, float]] = []
    for node in graph.nodes:
        if node == leaf:
            continue
        distance = _node_distance_m(graph, leaf, node)
        if distance <= snap_tolerance_m:
            candidates.append((node, distance))
    candidates.sort(key=lambda item: item[1])
    return candidates


def _should_snap(
    graph: nx.MultiDiGraph,
    leaf: int,
    target: int,
    leaf_edge: tuple[int, int, int, dict[str, Any]],
) -> bool:
    source, target_on_edge, _key, leaf_data = leaf_edge
    neighbor = target_on_edge if leaf == source else source
    leaf_osmid = _osmid_key(leaf_data.get("osmid"))

    for edge_source, edge_target, _edge_key, edge_data in graph.edges(
        target,
        keys=True,
        data=True,
    ):
        if edge_source == leaf or edge_target == leaf:
            continue
        target_osmid = _osmid_key(edge_data.get("osmid"))
        if leaf_osmid is not None and target_osmid == leaf_osmid:
            return True

    for edge_source, edge_target, _edge_key, edge_data in graph.in_edges(
        target,
        keys=True,
        data=True,
    ):
        if edge_source == leaf or edge_target == leaf:
            continue
        target_osmid = _osmid_key(edge_data.get("osmid"))
        if leaf_osmid is not None and target_osmid == leaf_osmid:
            return True

    other_end = neighbor
    leaf_bearing = _edge_bearing(graph, leaf, other_end)
    for edge_source, edge_target, _edge_key, _edge_data in graph.edges(
        target,
        keys=True,
        data=True,
    ):
        if edge_source == leaf or edge_target == leaf:
            continue
        other = edge_target if edge_source == target else edge_source
        target_bearing = _edge_bearing(graph, target, other)
        if _heading_compatible(leaf_bearing, target_bearing):
            return True

    for edge_source, edge_target, _edge_key, _edge_data in graph.in_edges(
        target,
        keys=True,
        data=True,
    ):
        if edge_source == leaf or edge_target == leaf:
            continue
        other = edge_source if edge_target == target else edge_target
        target_bearing = _edge_bearing(graph, target, other)
        if _heading_compatible(leaf_bearing, target_bearing):
            return True

    return leaf_osmid is None


def _contract_node(graph: nx.MultiDiGraph, survivor: int, leaf: int) -> None:
    if survivor == leaf or leaf not in graph:
        return

    leaf_data = graph.nodes[leaf]
    for key, value in leaf_data.items():
        if graph.nodes[survivor].get(key) in (None, "") and value not in (None, ""):
            graph.nodes[survivor][key] = value

    for source, target, key, data in list(graph.in_edges(leaf, keys=True, data=True)):
        new_source = survivor if source == leaf else source
        new_target = survivor if target == leaf else target
        if new_source == new_target:
            graph.remove_edge(source, target, key)
            continue
        length_m = float(data.get("length_m", data.get("length", 0.0)))
        if length_m <= 0:
            graph.remove_edge(source, target, key)
            continue
        new_key = key
        while graph.has_edge(new_source, new_target, new_key):
            new_key = new_key + 1 if isinstance(new_key, int) else 0
        graph.add_edge(new_source, new_target, key=new_key, **data)
        graph.remove_edge(source, target, key)

    for source, target, key, data in list(graph.out_edges(leaf, keys=True, data=True)):
        new_source = survivor if source == leaf else source
        new_target = survivor if target == leaf else target
        if new_source == new_target:
            graph.remove_edge(source, target, key)
            continue
        length_m = float(data.get("length_m", data.get("length", 0.0)))
        if length_m <= 0:
            graph.remove_edge(source, target, key)
            continue
        if graph.has_edge(source, target, key):
            continue
        new_key = key
        while graph.has_edge(new_source, new_target, new_key):
            new_key = new_key + 1 if isinstance(new_key, int) else 0
        graph.add_edge(new_source, new_target, key=new_key, **data)
        graph.remove_edge(source, target, key)

    if leaf in graph:
        graph.remove_node(leaf)


def _simplify_degree_two_same_osmid(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Merge degree-2 nodes whose in/out edges share the same osmid."""
    result = graph.copy()
    simplified = True
    while simplified:
        simplified = False
        for node in list(result.nodes):
            if result.degree(node) != 2:
                continue
            in_edges = list(result.in_edges(node, keys=True, data=True))
            out_edges = list(result.out_edges(node, keys=True, data=True))
            if len(in_edges) != 1 or len(out_edges) != 1:
                continue

            in_source, _in_target, in_key, in_data = in_edges[0]
            _out_source, out_target, out_key, out_data = out_edges[0]
            in_osmid = _osmid_key(in_data.get("osmid"))
            out_osmid = _osmid_key(out_data.get("osmid"))
            if in_osmid is None or in_osmid != out_osmid:
                continue

            source = in_source
            target = out_target
            result.remove_edge(in_source, node, in_key)
            result.remove_edge(node, out_target, out_key)
            result.remove_node(node)
            if source == target:
                simplified = True
                continue

            length_m = float(in_data.get("length_m", in_data.get("length", 0.0))) + float(
                out_data.get("length_m", out_data.get("length", 0.0))
            )
            merged = dict(in_data)
            for tag, value in out_data.items():
                if merged.get(tag) in (None, "") and value not in (None, ""):
                    merged[tag] = value
            merged["length_m"] = length_m
            merged["length"] = length_m
            new_key = 0
            while result.has_edge(source, target, new_key):
                new_key += 1
            result.add_edge(source, target, key=new_key, **merged)
            simplified = True
    return result


def _snap_endpoints(
    graph: nx.MultiDiGraph,
    snap_tolerance_m: float,
) -> nx.MultiDiGraph:
    result = graph.copy()
    snapped = True
    while snapped:
        snapped = False
        for leaf in _leaf_nodes(result):
            if leaf not in result:
                continue
            try:
                leaf_edge = _incident_edge(result, leaf)
            except ValueError:
                continue
            for candidate, _distance in _candidate_nodes(
                result,
                leaf,
                snap_tolerance_m=snap_tolerance_m,
            ):
                if candidate == leaf or candidate not in result:
                    continue
                if _should_snap(result, leaf, candidate, leaf_edge):
                    _contract_node(result, candidate, leaf)
                    snapped = True
                    break
    return result
