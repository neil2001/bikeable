import json
import pickle
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import networkx as nx
import osmnx as ox

GRAPH_VERSION = "4"


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


def save_qa_report(
    report: object,
    *,
    processed_root: Path,
    city_id: str,
) -> Path:
    paths = processed_graph_paths(processed_root, city_id)
    paths.city_dir.mkdir(parents=True, exist_ok=True)
    qa_path = paths.city_dir / "qa.json"
    payload = report.to_dict() if hasattr(report, "to_dict") else report
    qa_path.write_text(json.dumps(payload, indent=2) + "\n")
    return qa_path


def save_processed_graph(
    graph: nx.MultiDiGraph,
    *,
    processed_root: Path,
    city_id: str,
    source: str,
    paths: ProcessedGraphPaths | None = None,
) -> ProcessedGraphPaths:
    resolved_paths = paths or processed_graph_paths(processed_root, city_id)
    resolved_paths.city_dir.mkdir(parents=True, exist_ok=True)

    ox.save_graphml(graph, resolved_paths.graphml)
    resolved_paths.pickle.write_bytes(pickle.dumps(graph))

    metadata = {
        "cityId": city_id,
        "graphVersion": GRAPH_VERSION,
        "source": source,
        "builtAt": datetime.now(tz=UTC).isoformat(),
        "nodeCount": graph.number_of_nodes(),
        "edgeCount": graph.number_of_edges(),
    }
    resolved_paths.metadata.write_text(json.dumps(metadata, indent=2) + "\n")
    return resolved_paths


def load_processed_graph(paths: ProcessedGraphPaths) -> nx.MultiDiGraph:
    if paths.pickle.exists():
        return normalize_loaded_graph(pickle.loads(paths.pickle.read_bytes()))
    if paths.graphml.exists():
        return normalize_loaded_graph(ox.load_graphml(paths.graphml))
    msg = f"Processed graph not found at {paths.pickle} or {paths.graphml}"
    raise FileNotFoundError(msg)


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


def graph_cache_exists(paths: ProcessedGraphPaths) -> bool:
    return paths.pickle.exists() or paths.graphml.exists()
