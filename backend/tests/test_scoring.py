from app.features.builder import build_features
from app.graph.fixture import build_tiny_graph
from app.graph.loader import load_city_graph
from app.scoring.bike_graph import create_bike_graph
from app.scoring.config import load_scoring_config
from app.scoring.score import score_graph, score_road, score_road_detailed


def _edge(**attrs: object) -> dict[str, object]:
    base = {"highway": "residential", "length_m": 100.0, "surface": "asphalt"}
    base.update(attrs)
    return base


def test_protected_infrastructure_scores_higher_than_none() -> None:
    config = load_scoring_config()
    profile = config.profiles["road"]
    protected = build_features(_edge(**{"cycleway:both": "track"}))
    unprotected = build_features(_edge())
    assert score_road(protected, profile, config=config) > score_road(
        unprotected, profile, config=config
    )


def test_profile_weights_change_score_for_same_features() -> None:
    config = load_scoring_config()
    features = build_features(
        _edge(
            highway="primary",
            surface="gravel",
            maxspeed="40 mph",
            **{"cycleway:both": "track"},
        ),
    )
    road_score = score_road(features, config.profiles["road"], config=config)
    commuter_score = score_road(features, config.profiles["commuter"], config=config)
    assert road_score != commuter_score


def test_score_is_clamped_to_ten_point_scale() -> None:
    config = load_scoring_config()
    perfect = build_features(
        _edge(
            highway="cycleway",
            surface="asphalt",
            in_park=True,
            foot="yes",
            bicycle="designated",
        ),
    )
    score = score_road(perfect, config.profiles["leisure"], config=config)
    assert 0.0 <= score <= 10.0


def test_missing_traffic_does_not_drive_score_to_zero() -> None:
    config = load_scoring_config()
    features = build_features(_edge())
    assert features.traffic_volume is None
    assert features.traffic_imputed is True
    assert score_road(features, config.profiles["road"], config=config) > 0.0


def test_score_graph_writes_bikeability_on_fixture_edges() -> None:
    graph = load_city_graph("fixture")
    scored = score_graph(graph, "road")
    for _source, _target, _key, edge_data in scored.edges(keys=True, data=True):
        bikeability = edge_data["bikeability"]
        assert 0.0 <= bikeability <= 10.0
    assert scored.graph["score_version"] == "2"
    assert scored.graph["score_profile"] == "road"


def test_create_bike_graph_removes_non_traversable_edges() -> None:
    graph = build_tiny_graph()
    graph.add_edge(1, 2, key=1, highway="motorway", length_m=100.0)
    from app.features.apply import apply_features_to_graph

    apply_features_to_graph(graph)
    bike_graph = create_bike_graph(graph)
    assert bike_graph.number_of_edges() == graph.number_of_edges() - 1
    assert all(
        edge_data.get("highway") != "motorway"
        for *_rest, edge_data in bike_graph.edges(keys=True, data=True)
    )


def test_score_road_returns_reasons() -> None:
    config = load_scoring_config()
    features = build_features(
        _edge(
            highway="tertiary",
            maxspeed="30",
            oneway="yes",
            lanes="2",
            surface="asphalt",
            in_park=True,
        ),
    )
    breakdown = score_road_detailed(features, config.profiles["road"], config=config)
    assert "low speed" in breakdown.reasons
    assert "park environment" in breakdown.reasons
    assert "one-way road" in breakdown.reasons
