import networkx as nx

from app.config import settings
from app.features.apply import apply_features_to_graph
from app.graph.fixture import load_fixture_graph
from app.graph.ingest import download_city_graph, download_section_graph
from app.graph.registry import SectionDefinition, city_source_label, get_city_definition
from app.graph.stitch import stitch_graphs
from app.graph.store import (
    graph_cache_exists,
    load_processed_graph,
    processed_graph_paths,
    save_processed_graph,
    section_graph_paths,
)


class GraphPipelineError(Exception):
    """Raised when a city graph cannot be loaded or built."""


def _load_or_download_section(
    city_id: str,
    section: SectionDefinition,
    *,
    force_rebuild: bool,
) -> nx.MultiDiGraph:
    paths = section_graph_paths(settings.processed_data_dir, city_id, section.section_id)
    if not force_rebuild and graph_cache_exists(paths):
        return load_processed_graph(paths)

    graph = download_section_graph(section)
    save_processed_graph(
        graph,
        processed_root=settings.processed_data_dir,
        city_id=city_id,
        source=f"section:{section.section_id}",
        paths=paths,
    )
    return graph


def _build_sectioned_graph(
    city_id: str,
    sections: tuple[SectionDefinition, ...],
    *,
    force_rebuild: bool,
) -> nx.MultiDiGraph:
    section_graphs = [
        _load_or_download_section(city_id, section, force_rebuild=force_rebuild)
        for section in sections
    ]
    return stitch_graphs(section_graphs)


def load_city_graph(
    city_id: str,
    *,
    force_rebuild: bool = False,
) -> nx.MultiDiGraph:
    """Load a processed city graph from cache, building it when necessary."""
    city = get_city_definition(city_id)
    if city.is_fixture:
        return apply_features_to_graph(load_fixture_graph())

    paths = processed_graph_paths(settings.processed_data_dir, city_id)
    if not force_rebuild and graph_cache_exists(paths):
        return apply_features_to_graph(load_processed_graph(paths))

    if city.sections:
        graph = _build_sectioned_graph(city_id, city.sections, force_rebuild=force_rebuild)
    elif city.osm_bbox is not None or city.osm_place is not None:
        graph = download_city_graph(city)
    else:
        msg = f"City '{city_id}' does not define an OSM bbox, place query, or sections."
        raise GraphPipelineError(msg)

    graph = apply_features_to_graph(graph)
    save_processed_graph(
        graph,
        processed_root=settings.processed_data_dir,
        city_id=city_id,
        source=city_source_label(city),
    )
    return graph


def build_city_graph(city_id: str) -> nx.MultiDiGraph:
    """Download, preprocess, persist, and return a city graph."""
    return load_city_graph(city_id, force_rebuild=True)
