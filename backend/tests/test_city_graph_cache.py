from app.services.city_graph import (
    _bike_graph_cache,
    _scored_graph_cache,
    get_bikeability_overlay_path,
    get_scored_graph,
    get_scored_graph_for_bikeability,
    overlay_cache_path,
    reset_city_graph_caches,
)


def setup_function() -> None:
    reset_city_graph_caches()


def test_overlay_path_does_not_copy_bike_subgraph() -> None:
    path = overlay_cache_path("fixture", "road")
    if path.exists():
        path.unlink()
    get_bikeability_overlay_path("fixture", "road")
    assert len(_scored_graph_cache) == 1
    assert len(_bike_graph_cache) == 0


def test_graph_caches_keep_two_city_profile_slots() -> None:
    get_scored_graph_for_bikeability("fixture", "road")
    get_scored_graph_for_bikeability("fixture", "commuter")
    get_scored_graph_for_bikeability("fixture", "leisure")
    assert len(_scored_graph_cache) == 2
    remaining_profiles = {key[1] for key in _scored_graph_cache}
    assert remaining_profiles == {"commuter", "leisure"}


def test_routing_bike_copy_evicted_with_scored_graph() -> None:
    get_scored_graph("fixture", "road")
    get_scored_graph("fixture", "commuter")
    get_scored_graph("fixture", "leisure")
    assert len(_scored_graph_cache) == 2
    assert len(_bike_graph_cache) == 2
    assert all(key in _scored_graph_cache for key in _bike_graph_cache)
