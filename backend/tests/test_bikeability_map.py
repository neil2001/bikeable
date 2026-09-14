from app.features.apply import apply_features_to_graph, read_features_from_edge
from app.graph.fixture import build_tiny_graph
from app.models.common import CyclingProfile
from app.routing.ids import parse_road_id
from app.scoring.score import score_graph
from app.services.bikeability_map import graph_to_bikeability_geojson
from app.services.road_inspection import inspect_road


def _scored_fixture():
    graph = apply_features_to_graph(build_tiny_graph())
    return score_graph(graph, "road")


def test_overlay_collapses_bidirectional_pairs() -> None:
    scored = _scored_fixture()
    overlay = graph_to_bikeability_geojson(
        scored,
        city_id="fixture",
        score_version="2",
    )
    directed_traversable = sum(
        1
        for _source, _target, _key, edge_data in scored.edges(keys=True, data=True)
        if read_features_from_edge(edge_data).traversable
    )
    features = overlay["features"]
    assert overlay["type"] == "FeatureCollection"
    assert len(features) > 0
    assert len(features) <= directed_traversable
    assert len(features) < directed_traversable

    undirected_pairs = [
        tuple(sorted(parse_road_id(feature["properties"]["roadId"])[:2]))
        for feature in features
    ]
    assert len(undirected_pairs) == len(set(undirected_pairs))


def test_overlay_skips_non_traversable_edges() -> None:
    graph = apply_features_to_graph(build_tiny_graph())
    graph.add_node(5, lat=49.2800, lon=-123.1300, x=-100.0, y=0.0)
    graph.add_edge(1, 5, key=0, highway="motorway", length_m=100.0)
    graph.add_edge(5, 1, key=0, highway="motorway", length_m=100.0)
    scored = score_graph(apply_features_to_graph(graph), "road")
    overlay = graph_to_bikeability_geojson(
        scored,
        city_id="fixture",
        score_version="2",
    )
    road_ids = {feature["properties"]["roadId"] for feature in overlay["features"]}
    assert "1:5:0" not in road_ids
    assert "5:1:0" not in road_ids
    for feature in overlay["features"]:
        source, target, key = parse_road_id(feature["properties"]["roadId"])
        edge_data = scored.get_edge_data(source, target, key)
        assert edge_data is not None
        assert read_features_from_edge(edge_data).traversable is True


def test_overlay_road_ids_are_inspectable() -> None:
    scored = _scored_fixture()
    overlay = graph_to_bikeability_geojson(
        scored,
        city_id="fixture",
        score_version="2",
    )
    feature = overlay["features"][0]
    road_id = feature["properties"]["roadId"]
    assert "osmid" in feature["properties"]
    assert feature["id"] == feature["properties"]["osmid"]
    inspection = inspect_road(scored, road_id, CyclingProfile.ROAD)
    assert inspection.road_id == road_id
    assert 0 <= inspection.bikeability.score <= 10


def test_overlay_coordinates_use_six_decimals() -> None:
    scored = _scored_fixture()
    overlay = graph_to_bikeability_geojson(
        scored,
        city_id="fixture",
        score_version="2",
    )
    for feature in overlay["features"]:
        for lon, lat in feature["geometry"]["coordinates"]:
            assert lon == round(lon, 6)
            assert lat == round(lat, 6)
