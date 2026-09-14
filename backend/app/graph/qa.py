from __future__ import annotations

from dataclasses import asdict, dataclass, field

import networkx as nx

from app.features.normalize import coerce_tag


@dataclass
class NamedRoadGap:
    name: str
    component_count: int
    edge_count: int


@dataclass
class GraphQAReport:
    node_count: int
    edge_count: int
    weakly_connected_components: int
    largest_component_nodes: int
    largest_component_fraction: float
    named_road_gaps: list[NamedRoadGap] = field(default_factory=list)
    duplicate_osmid_pairs: int = 0
    leaf_nodes: int = 0
    broken_way_leaves: int = 0

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        return payload


def analyze_graph(graph: nx.MultiDiGraph) -> GraphQAReport:
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    components = list(nx.weakly_connected_components(graph))
    component_sizes = sorted((len(component) for component in components), reverse=True)
    largest = component_sizes[0] if component_sizes else 0
    fraction = (largest / node_count) if node_count else 0.0

    return GraphQAReport(
        node_count=node_count,
        edge_count=edge_count,
        weakly_connected_components=len(components),
        largest_component_nodes=largest,
        largest_component_fraction=round(fraction, 4),
        named_road_gaps=_named_road_gaps(graph),
        duplicate_osmid_pairs=_duplicate_osmid_pairs(graph),
        leaf_nodes=_leaf_count(graph),
        broken_way_leaves=_broken_way_leaves(graph),
    )


def format_qa_report(report: GraphQAReport) -> str:
    lines = [
        f"nodes: {report.node_count}",
        f"edges: {report.edge_count}",
        (
            f"weakly-connected components: {report.weakly_connected_components} "
            f"(largest {report.largest_component_nodes} "
            f"{report.largest_component_fraction:.1%})"
        ),
        f"leaf nodes: {report.leaf_nodes}",
        f"broken-way leaves: {report.broken_way_leaves}",
        f"duplicate osmid pairs: {report.duplicate_osmid_pairs}",
        f"named-road gaps: {len(report.named_road_gaps)}",
    ]
    for gap in report.named_road_gaps[:12]:
        lines.append(
            f"  - {gap.name}: {gap.component_count} components, {gap.edge_count} edges"
        )
    return "\n".join(lines)


def _osmid_set(value: object) -> set[int]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        items: set[int] = set()
        for item in value:
            items.update(_osmid_set(item))
        return items
    try:
        return {int(value)}
    except (TypeError, ValueError):
        return set()


def _named_road_gaps(graph: nx.MultiDiGraph) -> list[NamedRoadGap]:
    by_name: dict[str, list[tuple[int, int]]] = {}
    for source, target, _key, edge_data in graph.edges(keys=True, data=True):
        name = coerce_tag(edge_data.get("name"))
        if name is None:
            continue
        by_name.setdefault(name, []).append((source, target))

    gaps: list[NamedRoadGap] = []
    for name, pairs in by_name.items():
        if len(pairs) < 4:
            continue
        subgraph = nx.DiGraph()
        subgraph.add_edges_from(pairs)
        component_count = nx.number_weakly_connected_components(subgraph)
        if component_count > 1:
            gaps.append(
                NamedRoadGap(
                    name=name,
                    component_count=component_count,
                    edge_count=len(pairs),
                )
            )
    gaps.sort(key=lambda gap: (-gap.edge_count, gap.name))
    return gaps


def _duplicate_osmid_pairs(graph: nx.MultiDiGraph) -> int:
    seen: dict[tuple[int, int, int], int] = {}
    duplicates = 0
    for source, target, _key, edge_data in graph.edges(keys=True, data=True):
        for osmid in _osmid_set(edge_data.get("osmid")):
            key = (source, target, osmid)
            seen[key] = seen.get(key, 0) + 1
            if seen[key] == 2:
                duplicates += 1
    return duplicates


def _undirected_degree(graph: nx.MultiDiGraph, node: int) -> int:
    neighbors = set(graph.successors(node)) | set(graph.predecessors(node))
    neighbors.discard(node)
    return len(neighbors)


def _leaf_count(graph: nx.MultiDiGraph) -> int:
    return sum(1 for node in graph.nodes if _undirected_degree(graph, node) == 1)


def _broken_way_leaves(graph: nx.MultiDiGraph) -> int:
    """Leaves whose incident OSM way also appears on another edge (likely a cut)."""
    edges_by_osmid: dict[int, int] = {}
    for _source, _target, _key, edge_data in graph.edges(keys=True, data=True):
        for osmid in _osmid_set(edge_data.get("osmid")):
            edges_by_osmid[osmid] = edges_by_osmid.get(osmid, 0) + 1

    broken = 0
    for node in graph.nodes:
        if _undirected_degree(graph, node) != 1:
            continue
        osmids: set[int] = set()
        for _u, _v, _k, data in graph.edges(node, keys=True, data=True):
            osmids.update(_osmid_set(data.get("osmid")))
        for _u, _v, _k, data in graph.in_edges(node, keys=True, data=True):
            osmids.update(_osmid_set(data.get("osmid")))
        if any(edges_by_osmid.get(osmid, 0) > 2 for osmid in osmids):
            broken += 1
    return broken
