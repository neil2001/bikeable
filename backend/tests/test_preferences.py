import pytest
from app.features.builder import build_features
from app.main import app
from app.models.common import RoutePreferences
from app.routing.cost import edge_routing_cost
from app.scoring.config import RoutingCostParams, get_profile, load_scoring_config
from app.scoring.score import score_road
from fastapi.testclient import TestClient
from pydantic import ValidationError

client = TestClient(app)

VALID_SEGMENT = {
    "start": {"lat": 49.2800, "lon": -123.1200},
    "end": {"lat": 49.2820, "lon": -123.1000},
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


def test_distance_only_cost_equals_length() -> None:
    prefs = RoutePreferences(distance_weight=1.0, bikeability_weight=0.0)
    assert edge_routing_cost(250.0, 2.0, prefs) == pytest.approx(250.0)
    assert edge_routing_cost(250.0, 9.0, prefs) == pytest.approx(250.0)


def test_superlinear_cost_prefers_park_over_broadway() -> None:
    config = load_scoring_config()
    prefs = RoutePreferences(distance_weight=0.2, bikeability_weight=0.8)
    park = score_road(
        build_features(
            {
                "highway": "tertiary",
                "maxspeed": "30",
                "oneway": "yes",
                "lanes": "2",
                "bicycle": "yes",
                "surface": "asphalt",
                "in_park": True,
                "length_m": 100.0,
            },
        ),
        get_profile(config),
        config=config,
    )
    broadway = score_road(
        build_features(
            {
                "highway": "primary",
                "maxspeed": "50",
                "lanes": "4",
                "surface": "asphalt",
                "cycleway:both": "no",
                "length_m": 100.0,
            },
        ),
        get_profile(config),
        config=config,
    )
    park_cost = edge_routing_cost(100.0, park, prefs, routing=config.routing)
    broadway_cost = edge_routing_cost(100.0, broadway, prefs, routing=config.routing)
    assert park_cost < broadway_cost
    assert broadway_cost / park_cost >= 1.4


def test_routing_cost_does_not_divide_by_score() -> None:
    prefs = RoutePreferences(distance_weight=0.2, bikeability_weight=0.8)
    routing = RoutingCostParams(gamma=1.6, avoid_score=3.0, avoid_factor=1.3)
    low = edge_routing_cost(100.0, 0.2, prefs, routing=routing)
    high = edge_routing_cost(100.0, 9.0, prefs, routing=routing)
    assert low > high
    # 1/score would explode near 0 (~500+); superlinear discomfort stays bounded.
    assert low < 400
