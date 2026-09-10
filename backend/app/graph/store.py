import json
import pickle
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import networkx as nx
import osmnx as ox

GRAPH_VERSION = "1"


@dataclass(frozen=True)
class ProcessedGraphPaths:
    city_dir: Path
    graphml: Path
    pickle: Path
    metadata: Path


def processed_graph_paths(processed_root: Path, city_id: str) -> ProcessedGraphPaths:
    city_dir = processed_root / city_id
    return ProcessedGraphPaths(
        city_dir=city_dir,
        graphml=city_dir / "graph.graphml",
        pickle=city_dir / "graph.pkl",
        metadata=city_dir / "metadata.json",
    )


def save_processed_graph(
    graph: nx.MultiDiGraph,
    *,
    processed_root: Path,
    city_id: str,
    source: str,
) -> ProcessedGraphPaths:
    paths = processed_graph_paths(processed_root, city_id)
    paths.city_dir.mkdir(parents=True, exist_ok=True)

    ox.save_graphml(graph, paths.graphml)
    paths.pickle.write_bytes(pickle.dumps(graph))

    metadata = {
        "cityId": city_id,
        "graphVersion": GRAPH_VERSION,
        "source": source,
        "builtAt": datetime.now(tz=UTC).isoformat(),
        "nodeCount": graph.number_of_nodes(),
        "edgeCount": graph.number_of_edges(),
    }
    paths.metadata.write_text(json.dumps(metadata, indent=2) + "\n")
    return paths


def load_processed_graph(paths: ProcessedGraphPaths) -> nx.MultiDiGraph:
    if not paths.graphml.exists():
        msg = f"Processed graph not found at {paths.graphml}"
        raise FileNotFoundError(msg)
    return normalize_loaded_graph(ox.load_graphml(paths.graphml))


def normalize_loaded_graph(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    for _source, _target, _key, edge_data in graph.edges(keys=True, data=True):
        if "length_m" not in edge_data and "length" in edge_data:
            edge_data["length_m"] = float(edge_data["length"])
    return graph


def read_graph_metadata(paths: ProcessedGraphPaths) -> dict[str, object]:
    if not paths.metadata.exists():
        msg = f"Graph metadata not found at {paths.metadata}"
        raise FileNotFoundError(msg)
    return json.loads(paths.metadata.read_text())
