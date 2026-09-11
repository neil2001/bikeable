from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_bikeability_network_for_fixture_city() -> None:
    response = client.get("/api/v1/cities/fixture/bikeability?profile=road")
    assert response.status_code == 200
    payload = response.json()
    assert payload["cityId"] == "fixture"
    assert payload["scoreVersion"] == "2"
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) > 0
    feature = payload["features"][0]
    assert "roadId" in feature["properties"]
    assert "bikeability" in feature["properties"]
    assert feature["geometry"]["type"] == "LineString"
    scores = [item["properties"]["bikeability"] for item in payload["features"]]
    assert max(scores) > 5.0


def test_road_inspection_returns_score_components() -> None:
    network = client.get("/api/v1/cities/fixture/bikeability?profile=road").json()
    road_id = network["features"][0]["properties"]["roadId"]
    response = client.get(
        f"/api/v1/roads/{road_id}?cityId=fixture&profile=road",
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
