from app.features.apply import apply_features_to_graph
from app.graph.fixture import build_tiny_graph
from app.models.common import Coordinate, RoutePreferences
from app.routing.point_to_point import route_point_to_point
from app.scoring.score import score_graph


def _preferences(*, distance_weight: float) -> RoutePreferences:
    return RoutePreferences(
        distance_weight=distance_weight,
        bikeability_weight=1.0 - distance_weight,
    )


def test_bikeability_preference_avoids_primary_shortcut() -> None:
    graph = score_graph(apply_features_to_graph(build_tiny_graph()), "road")
    start = Coordinate(lat=49.2800, lon=-123.1200)
    end = Coordinate(lat=49.2820, lon=-123.1000)
    _path, metrics, _geometry = route_point_to_point(
        graph,
        start,
        end,
        _preferences(distance_weight=0.1),
    )
    assert metrics.average_bikeability >= 4.0
    assert metrics.distance_m > 1800
    assert 2 in _path


def test_distance_preference_uses_primary_shortcut() -> None:
    graph = score_graph(apply_features_to_graph(build_tiny_graph()), "road")
    start = Coordinate(lat=49.2800, lon=-123.1200)
    end = Coordinate(lat=49.2820, lon=-123.1000)
    _path, metrics, _geometry = route_point_to_point(
        graph,
        start,
        end,
        _preferences(distance_weight=0.95),
    )
    assert metrics.distance_m <= 1800


def test_unreachable_route_raises() -> None:
    graph = score_graph(apply_features_to_graph(build_tiny_graph()), "road")
    graph.add_node(99, lat=50.0, lon=-124.0, x=0.0, y=0.0)
    import pytest
    from app.routing.point_to_point import RoutingError

    with pytest.raises(RoutingError):
        route_point_to_point(
            graph,
            Coordinate(lat=49.2800, lon=-123.1200),
            Coordinate(lat=50.0, lon=-124.0),
            _preferences(distance_weight=0.5),
        )


def test_segment_api_returns_geometry() -> None:
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post(
        "/api/v1/routes/segment?cityId=fixture",
        json={
            "start": {"lat": 49.2800, "lon": -123.1200},
            "end": {"lat": 49.2820, "lon": -123.1000},
            "profile": "road",
            "preferences": {"distanceWeight": 0.2, "bikeabilityWeight": 0.8},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["geometry"]["type"] == "LineString"
    assert payload["distanceM"] > 0
