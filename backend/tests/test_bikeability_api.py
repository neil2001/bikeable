from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_bikeability_network_for_fixture_city() -> None:
    response = client.get("/api/v1/cities/fixture/bikeability?profile=road")
    assert response.status_code == 200
    payload = response.json()
    assert payload["cityId"] == "fixture"
    assert payload["scoreVersion"] == "1"
    assert len(payload["features"]) > 0
    feature = payload["features"][0]
    assert "roadId" in feature["properties"]
    assert "bikeability" in feature["properties"]
    assert feature["geometry"]["type"] == "LineString"


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
    assert "infrastructure" in payload["bikeability"]["components"]
