import gzip
import json
from collections import OrderedDict
from pathlib import Path

import networkx as nx
from app.config import settings
from app.graph.loader import GraphPipelineError, load_city_graph
from app.graph.registry import get_city_definition
from app.graph.store import (
    GRAPH_VERSION,
    graph_cache_exists,
    processed_graph_paths,
    read_graph_metadata,
)
from app.routing.index import attach_routing_index
from app.scoring.bike_graph import create_bike_graph
from app.scoring.config import cached_scoring_config
from app.scoring.score import score_graph
from app.services.bikeability_map import graph_to_bikeability_geojson

_CACHE_LIMIT = 2
OVERLAY_FORMAT_VERSION = "10"


class CityGraphUnavailableError(Exception):
    def __init__(self, city_id: str, reason: str) -> None:
        super().__init__(reason)
        self.city_id = city_id
        self.reason = reason


CacheKey = tuple[str, str, str]

_scored_graph_cache: OrderedDict[CacheKey, nx.MultiDiGraph] = OrderedDict()
_bike_graph_cache: OrderedDict[CacheKey, nx.MultiDiGraph] = OrderedDict()


def reset_city_graph_caches() -> None:
    _scored_graph_cache.clear()
    _bike_graph_cache.clear()


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


def _cache_key(city_id: str) -> CacheKey:
    return (
        city_id,
        _graph_version(city_id),
        str(cached_scoring_config().version),
    )


def _trim_graph_caches() -> None:
    while len(_scored_graph_cache) > _CACHE_LIMIT:
        evicted, _ = _scored_graph_cache.popitem(last=False)
        _bike_graph_cache.pop(evicted, None)


def _store_scored_graph(
    cache_key: CacheKey,
    graph: nx.MultiDiGraph,
) -> None:
    _scored_graph_cache[cache_key] = graph
    _scored_graph_cache.move_to_end(cache_key)
    _trim_graph_caches()


def _touch_cache_key(cache_key: CacheKey) -> None:
    if cache_key in _scored_graph_cache:
        _scored_graph_cache.move_to_end(cache_key)


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


def get_scored_graph(city_id: str) -> tuple[nx.MultiDiGraph, nx.MultiDiGraph]:
    cache_key = _cache_key(city_id)
    cached_scored = _scored_graph_cache.get(cache_key)
    cached_bike = _bike_graph_cache.get(cache_key)
    if cached_scored is not None and cached_bike is not None:
        _touch_cache_key(cache_key)
        return cached_scored, cached_bike

    scored = cached_scored
    if scored is None:
        graph = _load_base_graph(city_id)
        scored = score_graph(graph)
        _store_scored_graph(cache_key, scored)

    bike_graph = attach_routing_index(
        create_bike_graph(scored, allow_walk_links=True),
    )
    _bike_graph_cache[cache_key] = bike_graph
    _touch_cache_key(cache_key)
    return scored, bike_graph


def get_scored_graph_for_bikeability(city_id: str) -> nx.MultiDiGraph:
    cache_key = _cache_key(city_id)
    cached_scored = _scored_graph_cache.get(cache_key)
    if cached_scored is not None:
        _touch_cache_key(cache_key)
        return cached_scored

    graph = _load_base_graph(city_id)
    scored = score_graph(graph)
    _store_scored_graph(cache_key, scored)
    return scored


def overlay_cache_path(city_id: str) -> Path:
    city_id_key, graph_version, score_version = _cache_key(city_id)
    filename = (
        f"bikeability-g{graph_version}"
        f"-s{score_version}-o{OVERLAY_FORMAT_VERSION}.geojson.gz"
    )
    return settings.processed_data_dir / city_id_key / filename


def get_bikeability_overlay_path(city_id: str) -> Path:
    path = overlay_cache_path(city_id)
    if path.exists():
        return path

    scored = get_scored_graph_for_bikeability(city_id)
    payload = graph_to_bikeability_geojson(
        scored,
        city_id=city_id,
        score_version=str(scored.graph.get("score_version", "2")),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    with gzip.open(tmp_path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    tmp_path.replace(path)
    return path


def _overlay_bust_token(city_id: str) -> str:
    """Change when the processed graph is rebuilt so browser overlay caches miss."""
    paths = processed_graph_paths(settings.processed_data_dir, city_id)
    if not paths.metadata.exists():
        return "0"
    metadata = read_graph_metadata(paths)
    return f"{metadata.get('nodeCount', 0)}-{metadata.get('edgeCount', 0)}"


def bikeability_etag(city_id: str) -> str:
    city_id_key, graph_version, score_version = _cache_key(city_id)
    return (
        f'"{city_id_key}-{graph_version}-{score_version}-'
        f"{OVERLAY_FORMAT_VERSION}-{_overlay_bust_token(city_id)}\""
    )
