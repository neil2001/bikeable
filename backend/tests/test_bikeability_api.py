import networkx as nx
from app.features.apply import apply_features_to_graph
from app.main import app
from app.scoring.score import score_graph
from app.services.city_graph import OVERLAY_FORMAT_VERSION
from app.services.road_inspection import inspect_road
from fastapi.testclient import TestClient

client = TestClient(app)


def test_bikeability_returns_304_when_etag_matches() -> None:
    first = client.get("/api/v1/cities/fixture/bikeability")
    etag = first.headers["etag"]
    second = client.get(
        "/api/v1/cities/fixture/bikeability",
        headers={"If-None-Match": etag},
    )
    assert second.status_code == 304
    assert second.headers.get("etag") == etag
    assert second.content == b"" or not second.content


def test_bikeability_network_for_fixture_city() -> None:
    response = client.get("/api/v1/cities/fixture/bikeability")
    assert response.status_code == 200
    assert "etag" in response.headers
    assert f"-{OVERLAY_FORMAT_VERSION}-" in response.headers["etag"]
    payload = response.json()
    assert payload["cityId"] == "fixture"
    assert payload["scoreVersion"] == "2"
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) > 0
    feature = payload["features"][0]
    assert "roadId" in feature["properties"]
    assert "osmid" in feature["properties"]
    assert "bikeability" in feature["properties"]
    assert feature["geometry"]["type"] == "LineString"
    scores = [item["properties"]["bikeability"] for item in payload["features"]]
    assert max(scores) > 5.0


def test_inspect_expands_dropped_skip_edge() -> None:
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:32610"
    graph.add_node(10, lat=49.2775, lon=-123.2260, x=0.0, y=0.0)
    graph.add_node(20, lat=49.2776, lon=-123.2278, x=0.0, y=140.0)
    graph.add_node(30, lat=49.2783, lon=-123.2458, x=0.0, y=1500.0)
    graph.add_edge(
        10, 20, key=0, highway="tertiary", length_m=140.0, name="Northwest Marine Drive"
    )
    graph.add_edge(
        20,
        30,
        key=0,
        highway="tertiary",
        length_m=1360.0,
        name="Northwest Marine Drive",
    )
    scored = score_graph(apply_features_to_graph(graph))
    inspection = inspect_road(scored, "10:30:0")
    assert len(inspection.geometry.coordinates) >= 3
    assert inspection.road_id == "10:20:0"
    assert inspection.features.name == "Northwest Marine Drive"


def test_road_inspection_returns_score_components() -> None:
    network = client.get("/api/v1/cities/fixture/bikeability").json()
    road_id = network["features"][0]["properties"]["roadId"]
    response = client.get(
        f"/api/v1/roads/{road_id}?cityId=fixture",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["roadId"] == road_id
    assert 0 <= payload["bikeability"]["score"] <= 10
    components = payload["bikeability"]["components"]
    assert "infrastructure" in components
    assert "traffic" in components
    assert "environment" in components
    assert "context" in components
    assert isinstance(payload["bikeability"]["reasons"], list)


def test_inspect_road_surface_list_formatted() -> None:
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:32610"
    graph.add_node(1, lat=49.27, lon=-123.12, x=0.0, y=0.0)
    graph.add_node(2, lat=49.27, lon=-123.11, x=100.0, y=0.0)
    graph.add_edge(
        1,
        2,
        key=0,
        highway="residential",
        length_m=100.0,
        surface=["concrete", "paved"],
        name="Test Lane",
    )
    scored = score_graph(apply_features_to_graph(graph))
    inspection = inspect_road(scored, "1:2:0")
    assert inspection.features.surface is not None
    assert "concrete" in inspection.features.surface
    assert "paved" in inspection.features.surface


def test_inspect_road_surface_string_unchanged() -> None:
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:32610"
    graph.add_node(1, lat=49.27, lon=-123.12, x=0.0, y=0.0)
    graph.add_node(2, lat=49.27, lon=-123.11, x=100.0, y=0.0)
    graph.add_edge(
        1,
        2,
        key=0,
        highway="residential",
        length_m=100.0,
        surface="asphalt",
        name="Asphalt Lane",
    )
    scored = score_graph(apply_features_to_graph(graph))
    inspection = inspect_road(scored, "1:2:0")
    assert inspection.features.surface == "asphalt"
