from pathlib import Path

import networkx as nx

from app.config import settings
from app.features.apply import apply_features_to_graph
from app.graph.extract import OsmExtractError
from app.graph.fixture import load_fixture_graph
from app.graph.ingest import build_osm_graph
from app.graph.qa import analyze_graph
from app.graph.registry import city_source_label, get_city_definition
from app.graph.store import (
    graph_cache_exists,
    load_processed_graph,
    processed_graph_paths,
    save_processed_graph,
    save_qa_report,
)


class GraphPipelineError(Exception):
    """Raised when a city graph cannot be loaded or built."""


def _invalidate_city_derived_caches(city_id: str) -> None:
    city_dir = processed_graph_paths(settings.processed_data_dir, city_id).city_dir
    if city_dir.exists():
        for overlay in city_dir.glob("bikeability-*.geojson.gz"):
            overlay.unlink(missing_ok=True)
        for overlay in city_dir.glob("bikeability-*.pmtiles"):
            overlay.unlink(missing_ok=True)
    try:
        from app.services.city_graph import reset_city_graph_caches
    except ImportError:
        return
    reset_city_graph_caches()


def load_city_graph(
    city_id: str,
    *,
    force_rebuild: bool = False,
    osm_path: Path | None = None,
) -> nx.MultiDiGraph:
    """Load a processed city graph from cache, building it when necessary."""
    city = get_city_definition(city_id)
    if city.is_fixture:
        return apply_features_to_graph(load_fixture_graph())

    paths = processed_graph_paths(settings.processed_data_dir, city_id)
    if not force_rebuild and osm_path is None and graph_cache_exists(paths):
        return apply_features_to_graph(load_processed_graph(paths))

    if city.osm_bbox is None and osm_path is None:
        msg = f"City '{city_id}' does not define an OSM bbox or extract."
        raise GraphPipelineError(msg)

    try:
        graph = build_osm_graph(city, osm_path=osm_path)
    except (OsmExtractError, ValueError) as exc:
        raise GraphPipelineError(str(exc)) from exc

    graph = apply_features_to_graph(graph)
    save_processed_graph(
        graph,
        processed_root=settings.processed_data_dir,
        city_id=city_id,
        source=city_source_label(city) if osm_path is None else f"osm:{osm_path}",
    )
    save_qa_report(
        analyze_graph(graph),
        processed_root=settings.processed_data_dir,
        city_id=city_id,
    )
    _invalidate_city_derived_caches(city_id)
    return graph


def build_city_graph(
    city_id: str,
    *,
    osm_path: Path | None = None,
) -> nx.MultiDiGraph:
    """Build, persist, and return a city graph from a single OSM extract."""
    return load_city_graph(city_id, force_rebuild=True, osm_path=osm_path)
