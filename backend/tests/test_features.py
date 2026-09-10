import pytest
from app.features.apply import (
    apply_features_to_graph,
    feature_key,
    read_features_from_edge,
    write_features_to_edge,
)
from app.features.builder import build_features
from app.features.normalize import (
    collect_cycleway_tags,
    is_traversable,
    normalize_lane_count,
    normalize_speed_kph,
)
from app.graph.fixture import build_tiny_graph
from app.graph.loader import load_city_graph


def _edge(**attrs: object) -> dict[str, object]:
    base = {"highway": "residential", "length_m": 100.0}
    base.update(attrs)
    return base


def test_normalize_speed_handles_messy_values() -> None:
    assert normalize_speed_kph("30 mph") == pytest.approx(48.2802, rel=1e-3)
    assert normalize_speed_kph("50 km/h") == 50.0
    assert normalize_speed_kph("30") == 30.0
    assert normalize_speed_kph("signals") is None
    assert normalize_speed_kph(None) is None


def test_normalize_lanes_handles_multi_values() -> None:
    assert normalize_lane_count("2") == 2
    assert normalize_lane_count("2;3") == 3
    assert normalize_lane_count(None) is None


def test_cycleway_both_is_detected() -> None:
    edge = _edge(**{"cycleway:both": "lane"})
    tags = collect_cycleway_tags(edge)
    assert "lane" in tags
    features = build_features(edge)
    assert features.dedicated_bike_lane is True
    assert features.infrastructure_quality == 0.60


def test_protected_cycleway_scores_highest() -> None:
    edge = _edge(**{"cycleway:both": "track"})
    features = build_features(edge)
    assert features.protected_infrastructure is True
    assert features.infrastructure_quality == 1.00


def test_motorway_and_bicycle_no_are_not_traversable() -> None:
    assert is_traversable(_edge(highway="motorway")) is False
    assert is_traversable(_edge(bicycle="no")) is False
    assert is_traversable(_edge(highway="trunk")) is True


def test_missing_traffic_uses_neutral_comfort() -> None:
    features = build_features(_edge())
    assert features.traffic_volume is None
    assert features.traffic_comfort == 0.50
    assert features.traffic_confidence == 0.0


def test_quality_scores_are_within_unit_interval() -> None:
    samples = [
        _edge(highway="primary", maxspeed="45 mph", surface="gravel"),
        _edge(highway="cycleway", surface="asphalt", **{"cycleway:both": "track"}),
        _edge(highway="secondary", maxspeed="30", surface="unknown"),
    ]
    for edge in samples:
        features = build_features(edge)
        for attr in (
            "infrastructure_quality",
            "road_comfort",
            "speed_comfort",
            "traffic_comfort",
            "surface_quality",
            "grade_comfort",
        ):
            value = getattr(features, attr)
            assert 0.0 <= value <= 1.0, attr


def test_apply_features_writes_feat_namespace() -> None:
    graph = build_tiny_graph()
    apply_features_to_graph(graph)
    for _source, _target, _key, edge_data in graph.edges(keys=True, data=True):
        assert feature_key("traversable") in edge_data
        assert feature_key("road_comfort") in edge_data
        assert 0.0 <= edge_data[feature_key("road_comfort")] <= 1.0


def test_read_features_from_edge_round_trip() -> None:
    edge = _edge(maxspeed="30 mph", surface="asphalt")
    features = build_features(edge)
    edge_data = dict(edge)
    write_features_to_edge(edge_data, features)
    restored = read_features_from_edge(edge_data)
    assert restored.infrastructure_quality == features.infrastructure_quality
    assert restored.speed_kph == pytest.approx(features.speed_kph)


def test_fixture_graph_load_includes_features() -> None:
    graph = load_city_graph("fixture")
    for _source, _target, _key, edge_data in graph.edges(keys=True, data=True):
        assert edge_data[feature_key("traversable")] is True
        assert edge_data[feature_key("highway_class")] == "residential"
