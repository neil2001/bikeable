from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_from_roads_assembles_connected_fixture_walk() -> None:
    response = client.post(
        "/api/v1/routes/from-roads?cityId=fixture",
        json={"roadIds": ["1:2:0", "2:3:0"], "profile": "road"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["distanceM"] == 2000.0
    assert payload["geometry"]["type"] == "LineString"
    assert payload["routeId"].startswith("rt_")

    gpx = client.get(f"/api/v1/routes/{payload['routeId']}/gpx")
    assert gpx.status_code == 200
    assert "gpx" in gpx.headers["content-type"]
    assert b"<gpx" in gpx.content


def test_from_roads_rejects_disconnected_roads() -> None:
    response = client.post(
        "/api/v1/routes/from-roads?cityId=fixture",
        json={"roadIds": ["1:2:0", "3:4:0"], "profile": "road"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_from_roads_rejects_unknown_road() -> None:
    response = client.post(
        "/api/v1/routes/from-roads?cityId=fixture",
        json={"roadIds": ["99:100:0"], "profile": "road"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_from_roads_rejects_invalid_road_id() -> None:
    response = client.post(
        "/api/v1/routes/from-roads?cityId=fixture",
        json={"roadIds": ["not-a-road"], "profile": "road"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
