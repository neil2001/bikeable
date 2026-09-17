from __future__ import annotations

from collections import defaultdict

import networkx as nx

from app.features.normalize import (
    coerce_tag,
    is_traversable,
    is_unmarked_pedestrian_way,
)

CONNECTOR_DETOUR_M = 400.0
CONNECTOR_DETOUR_RATIO = 15.0


def _edge_length_m(edge_data: dict) -> float:
    length = edge_data.get("length_m")
    if length is not None:
        return float(length)
    length = edge_data.get("length")
    if length is not None:
        return float(length)
    return 1.0


def _build_bikeable_digraph(graph: nx.MultiDiGraph) -> nx.DiGraph:
    bikeable = nx.DiGraph()
    for source, target, _key, edge_data in graph.edges(keys=True, data=True):
        if not is_traversable(edge_data):
            continue
        length = _edge_length_m(edge_data)
        if bikeable.has_edge(source, target):
            bikeable[source][target]["length"] = min(
                bikeable[source][target]["length"],
                length,
            )
        else:
            bikeable.add_edge(source, target, length=length)
    return bikeable


def mark_necessary_connectors(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Flag unmarked pedestrian edges that are high-detour shortcuts on graph B."""
    bikeable = _build_bikeable_digraph(graph)
    b_nodes = set(bikeable.nodes())

    candidates: list[tuple[int, int, int, float]] = []
    for source, target, key, edge_data in graph.edges(keys=True, data=True):
        if coerce_tag(edge_data.get("access")) == "private":
            edge_data["necessary_connector"] = False
            continue
        if not is_unmarked_pedestrian_way(edge_data):
            edge_data["necessary_connector"] = False
            continue
        if source not in b_nodes or target not in b_nodes:
            edge_data["necessary_connector"] = False
            continue
        length = _edge_length_m(edge_data)
        candidates.append((source, target, key, length))

    by_source: dict[int, list[tuple[int, int, float, float]]] = defaultdict(list)
    for source, target, key, length in candidates:
        threshold = max(CONNECTOR_DETOUR_M, CONNECTOR_DETOUR_RATIO * length)
        by_source[source].append((target, key, length, threshold))

    for source, dests in by_source.items():
        max_cutoff = max(threshold for _, _, _, threshold in dests)
        lengths = nx.single_source_dijkstra_path_length(
            bikeable,
            source,
            cutoff=max_cutoff,
            weight="length",
        )
        for target, key, _length, threshold in dests:
            dist = lengths.get(target)
            necessary = dist is None or dist > threshold
            graph[source][target][key]["necessary_connector"] = necessary

    return graph
