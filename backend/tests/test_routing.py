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
    graph = score_graph(apply_features_to_graph(build_tiny_graph()))
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


def test_preferences_change_path_without_mutating_graph() -> None:
    graph = score_graph(apply_features_to_graph(build_tiny_graph()))
    start = Coordinate(lat=49.2800, lon=-123.1200)
    end = Coordinate(lat=49.2820, lon=-123.1000)
    bike_path, bike_metrics, _ = route_point_to_point(
        graph,
        start,
        end,
        _preferences(distance_weight=0.1),
    )
    dist_path, dist_metrics, _ = route_point_to_point(
        graph,
        start,
        end,
        _preferences(distance_weight=0.95),
    )
    assert dist_metrics.distance_m < bike_metrics.distance_m
    assert dist_path != bike_path


def test_distance_preference_uses_primary_shortcut() -> None:
    graph = score_graph(apply_features_to_graph(build_tiny_graph()))
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
    graph = score_graph(apply_features_to_graph(build_tiny_graph()))
    graph.add_node(99, lat=49.2810, lon=-123.1210, x=-80.0, y=80.0)
    graph.add_node(100, lat=49.2815, lon=-123.1215, x=-120.0, y=120.0)
    graph.add_edge(
        99, 100, key=0, highway="residential", length_m=60.0, bikeability=6.0
    )
    graph.add_edge(
        100, 99, key=0, highway="residential", length_m=60.0, bikeability=6.0
    )
    import pytest
    from app.routing.point_to_point import RoutingError

    with pytest.raises(RoutingError) as exc:
        route_point_to_point(
            graph,
            Coordinate(lat=49.2800, lon=-123.1200),
            Coordinate(lat=49.2810, lon=-123.1210),
            _preferences(distance_weight=0.5),
        )
    assert exc.value.code == "ROUTE_NOT_FOUND"
    assert "disconnected" in exc.value.message


def test_far_from_network_raises_invalid_coordinates() -> None:
    graph = score_graph(apply_features_to_graph(build_tiny_graph()))
    import pytest
    from app.routing.point_to_point import RoutingError

    with pytest.raises(RoutingError) as exc:
        route_point_to_point(
            graph,
            Coordinate(lat=49.2800, lon=-123.1200),
            Coordinate(lat=50.0, lon=-124.0),
            _preferences(distance_weight=0.5),
        )
    assert exc.value.code == "INVALID_COORDINATES"


def test_segment_api_returns_geometry() -> None:
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post(
        "/api/v1/routes/segment?cityId=fixture",
        json={
            "start": {"lat": 49.2800, "lon": -123.1200},
            "end": {"lat": 49.2820, "lon": -123.1000},
            "preferences": {"distanceWeight": 0.2, "bikeabilityWeight": 0.8},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["geometry"]["type"] == "LineString"
    assert payload["distanceM"] > 0
