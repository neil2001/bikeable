from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_end_to_end_fixture_workflow() -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200

    network = client.get("/api/v1/cities/fixture/bikeability")
    assert network.status_code == 200
    assert network.json()["features"]

    segment = client.post(
        "/api/v1/routes/segment?cityId=fixture",
        json={
            "start": {"lat": 49.2800, "lon": -123.1200},
            "end": {"lat": 49.2820, "lon": -123.1000},
            "preferences": {"distanceWeight": 0.2, "bikeabilityWeight": 0.8},
        },
    )
    assert segment.status_code == 200

    loop = client.post(
        "/api/v1/routes/loop?cityId=fixture",
        json={
            "start": {"lat": 49.2800, "lon": -123.1200},
            "targetDistanceM": 4900,
            "preferences": {"distanceWeight": 0.2, "bikeabilityWeight": 0.8},
            "constraints": {"minDistanceM": 4000, "maxDistanceM": 6000},
        },
    )
    assert loop.status_code == 200
    route_id = loop.json()["routeId"]

    gpx = client.get(f"/api/v1/routes/{route_id}/gpx")
    assert gpx.status_code == 200
    assert "<gpx" in gpx.text
