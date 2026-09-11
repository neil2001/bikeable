import networkx as nx
from app.config import settings
from app.graph.loader import GraphPipelineError, load_city_graph
from app.graph.registry import get_city_definition
from app.graph.store import GRAPH_VERSION, graph_cache_exists, processed_graph_paths, read_graph_metadata
from app.models.responses import BikeabilityNetworkResponse
from app.scoring.bike_graph import create_bike_graph
from app.scoring.config import cached_scoring_config
from app.scoring.score import score_graph
from app.services.bikeability_map import graph_to_bikeability_response


class CityGraphUnavailableError(Exception):
    def __init__(self, city_id: str, reason: str) -> None:
        super().__init__(reason)
        self.city_id = city_id
        self.reason = reason


_scored_graph_cache: dict[tuple[str, str, str, str], nx.MultiDiGraph] = {}
_bike_graph_cache: dict[tuple[str, str, str, str], nx.MultiDiGraph] = {}
_overlay_cache: dict[tuple[str, str, str, str], BikeabilityNetworkResponse] = {}


def city_graph_is_available(city_id: str) -> bool:
    city = get_city_definition(city_id)
    if city.is_fixture:
        return True
    paths = processed_graph_paths(settings.processed_data_dir, city_id)
    return graph_cache_exists(paths)


def _graph_version(city_id: str) -> str:
    paths = processed_graph_paths(settings.processed_data_dir, city_id)
    if paths.metadata.exists():
        metadata = read_graph_metadata(paths)
        return str(metadata.get("graphVersion", GRAPH_VERSION))
    return GRAPH_VERSION


def _cache_key(city_id: str, profile_id: str) -> tuple[str, str, str, str]:
    return (
        city_id,
        profile_id,
        _graph_version(city_id),
        str(cached_scoring_config().version),
    )


def _load_base_graph(city_id: str) -> nx.MultiDiGraph:
    try:
        get_city_definition(city_id)
    except KeyError as exc:
        raise CityGraphUnavailableError(city_id, str(exc)) from exc

    if not city_graph_is_available(city_id):
        raise CityGraphUnavailableError(
            city_id,
            f"Processed graph for '{city_id}' has not been built yet.",
        )

    try:
        return load_city_graph(city_id)
    except (FileNotFoundError, GraphPipelineError) as exc:
        raise CityGraphUnavailableError(city_id, str(exc)) from exc


def get_scored_graph(
    city_id: str,
    profile_id: str,
) -> tuple[nx.MultiDiGraph, nx.MultiDiGraph]:
    cache_key = _cache_key(city_id, profile_id)
    cached_scored = _scored_graph_cache.get(cache_key)
    cached_bike = _bike_graph_cache.get(cache_key)
    if cached_scored is not None and cached_bike is not None:
        return cached_scored, cached_bike

    graph = _load_base_graph(city_id)
    scored = score_graph(graph, profile_id)
    bike_graph = create_bike_graph(scored)
    _scored_graph_cache[cache_key] = scored
    _bike_graph_cache[cache_key] = bike_graph
    return scored, bike_graph


def get_scored_graph_for_bikeability(
    city_id: str,
    profile_id: str,
) -> nx.MultiDiGraph:
    cache_key = _cache_key(city_id, profile_id)
    cached_scored = _scored_graph_cache.get(cache_key)
    if cached_scored is not None:
        return cached_scored

    graph = _load_base_graph(city_id)
    scored = score_graph(graph, profile_id)
    _scored_graph_cache[cache_key] = scored
    return scored


def get_bikeability_overlay(
    city_id: str,
    profile_id: str,
) -> BikeabilityNetworkResponse:
    cache_key = _cache_key(city_id, profile_id)
    cached_overlay = _overlay_cache.get(cache_key)
    if cached_overlay is not None:
        return cached_overlay

    scored = get_scored_graph_for_bikeability(city_id, profile_id)
    overlay = graph_to_bikeability_response(
        scored,
        city_id=city_id,
        score_version=str(scored.graph.get("score_version", "2")),
    )
    _overlay_cache[cache_key] = overlay
    return overlay


def bikeability_etag(city_id: str, profile_id: str) -> str:
    city_id_key, profile_key, graph_version, score_version = _cache_key(city_id, profile_id)
    return f'"{city_id_key}-{graph_version}-{score_version}-{profile_key}"'
