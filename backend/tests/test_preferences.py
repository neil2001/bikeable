import pytest
from app.main import app
from app.models.common import RoutePreferences
from fastapi.testclient import TestClient
from pydantic import ValidationError

client = TestClient(app)

VALID_SEGMENT = {
    "start": {"lat": 49.2827, "lon": -123.1207},
    "end": {"lat": 49.273, "lon": -123.1},
    "profile": "road",
    "preferences": {"distanceWeight": 0.2, "bikeabilityWeight": 0.8},
}


def test_preferences_accept_weights_that_sum_to_one() -> None:
    prefs = RoutePreferences(distance_weight=0.35, bikeability_weight=0.65)
    assert prefs.distance_weight + prefs.bikeability_weight == pytest.approx(1.0)


def test_preferences_reject_weights_that_do_not_sum_to_one() -> None:
    with pytest.raises(ValidationError, match="must equal 1"):
        RoutePreferences(distance_weight=0.5, bikeability_weight=0.6)


def test_segment_endpoint_validates_preference_weights() -> None:
    body = {
        **VALID_SEGMENT,
        "preferences": {"distanceWeight": 0.9, "bikeabilityWeight": 0.2},
    }
    response = client.post("/api/v1/routes/segment", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_segment_endpoint_accepts_valid_weights_and_routes() -> None:
    response = client.post(
        "/api/v1/routes/segment?cityId=fixture",
        json=VALID_SEGMENT,
    )
    assert response.status_code == 200
    assert response.json()["distanceM"] > 0
