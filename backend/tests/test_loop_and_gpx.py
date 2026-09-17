from app.export.gpx import route_to_gpx
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

LOOP_REQUEST = {
    "start": {"lat": 49.2800, "lon": -123.1200},
    "targetDistanceM": 4900,
    "preferences": {"distanceWeight": 0.2, "bikeabilityWeight": 0.8},
    "constraints": {"minDistanceM": 4000, "maxDistanceM": 6000},
}


def test_loop_generation_returns_route() -> None:
    response = client.post("/api/v1/routes/loop?cityId=fixture", json=LOOP_REQUEST)
    assert response.status_code == 200
    payload = response.json()
    assert payload["routeId"]
    assert payload["distanceM"] >= 4000
    assert payload["distanceM"] <= 6000
    assert len(payload["profile"]) >= 2
    assert payload["optimization"]["algorithmVersion"] == "loop-heuristic-v1"


def test_gpx_export_after_loop() -> None:
    route = client.post("/api/v1/routes/loop?cityId=fixture", json=LOOP_REQUEST).json()
    response = client.get(f"/api/v1/routes/{route['routeId']}/gpx")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/gpx+xml")
    assert "<gpx" in response.text
    assert "<trkpt" in response.text


def test_route_to_gpx_contains_trackpoints() -> None:
    from app.models.common import GeoJSONLineString
    from app.models.responses import RouteProfileSample, RouteResponse

    route = RouteResponse(
        route_id="test",
        geometry=GeoJSONLineString(
            coordinates=[[-123.12, 49.28], [-123.11, 49.281]],
        ),
        distance_m=1000,
        elevation_gain_m=0,
        average_bikeability=8,
        pct_high_quality=0.9,
        pct_bad_roads=0.01,
        pct_protected=0.2,
        high_speed_exposure=0.01,
        hostile_intersections=0,
        score=8,
        profile=[RouteProfileSample(distance_m=0, elevation_m=10, bikeability=8)],
    )
    gpx = route_to_gpx(route)
    assert gpx.count("<trkpt") == 2
