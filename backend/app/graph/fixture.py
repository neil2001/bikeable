from pathlib import Path

import networkx as nx
import osmnx as ox

from app.graph.ingest import normalize_graph

FIXTURE_GRAPHML = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "tiny_graph.graphml"
)


def build_tiny_graph() -> nx.MultiDiGraph:
    """Hand-built graph used for deterministic tests.

    Layout:
        1 ─── 2 ─── 3
        │           │
        └──── 4 ────┘
    """
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:32610"

    nodes = {
        1: {"lat": 49.2800, "lon": -123.1200, "x": 0.0, "y": 0.0},
        2: {"lat": 49.2810, "lon": -123.1100, "x": 1000.0, "y": 0.0},
        3: {"lat": 49.2820, "lon": -123.1000, "x": 2000.0, "y": 100.0},
        4: {"lat": 49.2790, "lon": -123.1050, "x": 1500.0, "y": -200.0},
    }
    for node_id, attrs in nodes.items():
        graph.add_node(node_id, **attrs)

    edges = [
        (1, 2, {"highway": "residential", "length_m": 1000.0}),
        (2, 3, {"highway": "residential", "length_m": 1000.0}),
        (3, 4, {"highway": "residential", "length_m": 1414.0}),
        (4, 1, {"highway": "residential", "length_m": 1500.0}),
    ]
    for source, target, attrs in edges:
        graph.add_edge(source, target, **attrs)

    return normalize_graph(graph)


def load_fixture_graph() -> nx.MultiDiGraph:
    if FIXTURE_GRAPHML.exists():
        return normalize_graph(ox.load_graphml(FIXTURE_GRAPHML))
    return build_tiny_graph()


def write_fixture_graphml(path: Path | None = None) -> Path:
    target = path or FIXTURE_GRAPHML
    target.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(build_tiny_graph(), target)
    return target
