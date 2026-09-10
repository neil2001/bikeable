import networkx as nx

from app.config import settings
from app.features.apply import apply_features_to_graph
from app.graph.fixture import load_fixture_graph
from app.graph.ingest import download_city_graph
from app.graph.registry import get_city_definition
from app.graph.store import (
    load_processed_graph,
    processed_graph_paths,
    save_processed_graph,
)


class GraphPipelineError(Exception):
    """Raised when a city graph cannot be loaded or built."""


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
    if not force_rebuild and paths.graphml.exists():
        return apply_features_to_graph(load_processed_graph(paths))

    if city.osm_place is None:
        msg = f"City '{city_id}' does not define an OSM place query."
        raise GraphPipelineError(msg)

    graph = apply_features_to_graph(download_city_graph(city.osm_place))
    save_processed_graph(
        graph,
        processed_root=settings.processed_data_dir,
        city_id=city_id,
        source=city.osm_place,
    )
    return graph


def build_city_graph(city_id: str) -> nx.MultiDiGraph:
    """Download, preprocess, persist, and return a city graph."""
    return load_city_graph(city_id, force_rebuild=True)
