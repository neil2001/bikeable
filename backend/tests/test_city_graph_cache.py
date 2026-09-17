from app.routing.index import ROUTING_INDEX_KEY, RoutingIndex
from app.services.city_graph import (
    OVERLAY_FORMAT_VERSION,
    _bike_graph_cache,
    _scored_graph_cache,
    bikeability_etag,
    get_bikeability_overlay_path,
    get_scored_graph,
    get_scored_graph_for_bikeability,
    overlay_cache_path,
    reset_city_graph_caches,
)


def setup_function() -> None:
    reset_city_graph_caches()


def test_bikeability_etag_includes_overlay_format_version() -> None:
    etag = bikeability_etag("fixture")
    assert OVERLAY_FORMAT_VERSION in etag


def test_bikeability_etag_changes_when_processed_graph_is_rebuilt(
    tmp_path, monkeypatch
) -> None:
    from app.config import settings
    from app.graph.fixture import build_tiny_graph
    from app.graph.store import save_processed_graph

    monkeypatch.setattr(settings, "data_root", tmp_path)
    graph = build_tiny_graph()
    save_processed_graph(
        graph,
        processed_root=settings.processed_data_dir,
        city_id="vancouver",
        source="test",
    )
    first = bikeability_etag("vancouver")
    graph.add_node(99, lat=49.28, lon=-123.12, x=0.0, y=0.0)
    save_processed_graph(
        graph,
        processed_root=settings.processed_data_dir,
        city_id="vancouver",
        source="test",
    )
    second = bikeability_etag("vancouver")
    assert first != second


def test_overlay_path_does_not_copy_bike_subgraph() -> None:
    path = overlay_cache_path("fixture")
    if path.exists():
        path.unlink()
    get_bikeability_overlay_path("fixture")
    assert len(_scored_graph_cache) == 1
    assert len(_bike_graph_cache) == 0


def _save_vancouver_fixture_graph(tmp_path, monkeypatch) -> None:
    from app.config import settings
    from app.graph.fixture import build_tiny_graph
    from app.graph.store import save_processed_graph

    monkeypatch.setattr(settings, "data_root", tmp_path)
    save_processed_graph(
        build_tiny_graph(),
        processed_root=settings.processed_data_dir,
        city_id="vancouver",
        source="test",
    )


def test_graph_caches_keep_two_city_slots(tmp_path, monkeypatch) -> None:
    _save_vancouver_fixture_graph(tmp_path, monkeypatch)
    get_scored_graph_for_bikeability("fixture")
    get_scored_graph_for_bikeability("vancouver")
    assert len(_scored_graph_cache) == 2
    remaining_cities = {key[0] for key in _scored_graph_cache}
    assert remaining_cities == {"fixture", "vancouver"}


def test_get_scored_graph_attaches_routing_index() -> None:
    _scored, bike_graph = get_scored_graph("fixture")
    assert isinstance(bike_graph.graph.get(ROUTING_INDEX_KEY), RoutingIndex)


def test_routing_bike_copy_evicted_with_scored_graph(tmp_path, monkeypatch) -> None:
    _save_vancouver_fixture_graph(tmp_path, monkeypatch)
    get_scored_graph("fixture")
    get_scored_graph("vancouver")
    assert len(_scored_graph_cache) == 2
    assert len(_bike_graph_cache) == 2
    assert all(key in _scored_graph_cache for key in _bike_graph_cache)
