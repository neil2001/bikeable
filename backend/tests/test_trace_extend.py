from __future__ import annotations

import networkx as nx
from app.features.apply import apply_features_to_graph
from app.graph.fixture import build_tiny_graph
from app.main import app
from app.models.common import Coordinate, RoutePreferences
from app.routing.ids import make_road_id
from app.routing.trace import extend_trace
from app.scoring.score import score_graph
from fastapi.testclient import TestClient

client = TestClient(app)

PREFERENCES = RoutePreferences(distance_weight=0.2, bikeability_weight=0.8)
PREFERENCES_JSON = {"distanceWeight": 0.2, "bikeabilityWeight": 0.8}


def _score(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    return score_graph(apply_features_to_graph(graph), "road")


def _add_node(
    graph: nx.MultiDiGraph, node_id: int, *, lat: float, lon: float, x: float
) -> None:
    graph.add_node(node_id, lat=lat, lon=lon, x=x, y=0.0)


def _add_bidirectional(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    **attrs,
) -> None:
    graph.add_edge(source, target, **attrs)
    graph.add_edge(target, source, **attrs)


def _named_network() -> nx.MultiDiGraph:
    """4th Ave corridor with a Broadway spur and an Oak Street gap.

    1 --4th-- 2 --4th-- 3 --4th-- 4 --Oak-- 5 --4th-- 6
                    |
                 Broadway
                    |
                    7 --Broadway-- 8
    """
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:32610"
    coords = {
        1: (49.2800, -123.1200, 0.0),
        2: (49.2800, -123.1100, 1000.0),
        3: (49.2800, -123.1000, 2000.0),
        4: (49.2800, -123.0900, 3000.0),
        5: (49.2800, -123.0800, 4000.0),
        6: (49.2800, -123.0700, 5000.0),
        7: (49.2720, -123.1000, 2000.0),
        8: (49.2640, -123.1000, 2000.0),
    }
    for node_id, (lat, lon, x) in coords.items():
        _add_node(graph, node_id, lat=lat, lon=lon, x=x)

    fourth = {
        "highway": "residential",
        "length_m": 1000.0,
        "name": "West 4th Avenue",
        "osmid": 10,
    }
    oak = {
        "highway": "residential",
        "length_m": 1000.0,
        "name": "Oak Street",
        "osmid": 20,
    }
    broadway = {
        "highway": "residential",
        "length_m": 900.0,
        "name": "Broadway",
        "osmid": 30,
    }
    _add_bidirectional(graph, 1, 2, **fourth)
    _add_bidirectional(graph, 2, 3, **fourth)
    _add_bidirectional(graph, 3, 4, **fourth)
    _add_bidirectional(graph, 4, 5, **oak)
    _add_bidirectional(graph, 5, 6, **{**fourth, "osmid": 11})
    _add_bidirectional(graph, 3, 7, **broadway)
    _add_bidirectional(graph, 7, 8, **{**broadway, "osmid": 31})
    return graph


def _unnamed_osmid_corridor() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:32610"
    for node_id, x in ((1, 0.0), (2, 1000.0), (3, 2000.0), (4, 3000.0)):
        _add_node(graph, node_id, lat=49.26, lon=-123.12 + node_id * 0.01, x=x)
    attrs = {"highway": "residential", "length_m": 1000.0, "osmid": 99}
    _add_bidirectional(graph, 1, 2, **attrs)
    _add_bidirectional(graph, 2, 3, **attrs)
    _add_bidirectional(graph, 3, 4, **attrs)
    return graph


def _orientations(graph: nx.MultiDiGraph, source: int, target: int, key: int = 0):
    found = []
    if graph.has_edge(source, target, key):
        found.append((source, target, key))
    if graph.has_edge(target, source, key):
        found.append((target, source, key))
    return found


def test_empty_path_selects_clicked_edge() -> None:
    graph = _score(_named_network())
    result = extend_trace(
        graph,
        [],
        _orientations(graph, 1, 2),
        start=None,
        preferences=PREFERENCES,
        head_only=False,
    )
    assert result.action == "select"
    assert result.edges == [(1, 2, 0)]


def test_empty_path_with_start_routes_through_clicked() -> None:
    graph = _score(_named_network())
    result = extend_trace(
        graph,
        [],
        _orientations(graph, 3, 4),
        start=Coordinate(lat=49.2800, lon=-123.1200),
        preferences=PREFERENCES,
        head_only=True,
    )
    assert result.action == "route"
    assert result.edges[0][0] == 1
    assert result.edges[-1] == (3, 4, 0)
    assert (1, 2, 0) in result.edges
    assert (2, 3, 0) in result.edges


def test_same_name_skip_ahead_fills_intervening_edges() -> None:
    graph = _score(_named_network())
    result = extend_trace(
        graph,
        [(1, 2, 0)],
        _orientations(graph, 3, 4),
        start=None,
        preferences=PREFERENCES,
        head_only=False,
    )
    assert result.action == "same_road"
    assert result.edges == [(1, 2, 0), (2, 3, 0), (3, 4, 0)]


def test_unnamed_same_osmid_fills_corridor() -> None:
    graph = _score(_unnamed_osmid_corridor())
    result = extend_trace(
        graph,
        [(1, 2, 0)],
        _orientations(graph, 3, 4),
        start=None,
        preferences=PREFERENCES,
        head_only=False,
    )
    assert result.action == "same_road"
    assert result.edges == [(1, 2, 0), (2, 3, 0), (3, 4, 0)]


def test_different_name_uses_bikeable_connector() -> None:
    graph = _score(_named_network())
    result = extend_trace(
        graph,
        [(1, 2, 0)],
        _orientations(graph, 7, 8),
        start=None,
        preferences=PREFERENCES,
        head_only=False,
    )
    assert result.action == "route"
    assert result.edges[0] == (1, 2, 0)
    assert result.edges[-1] == (7, 8, 0)
    assert (2, 3, 0) in result.edges
    assert (3, 7, 0) in result.edges


def test_interrupted_same_name_falls_through_to_bikeable_route() -> None:
    graph = _score(_named_network())
    result = extend_trace(
        graph,
        [(1, 2, 0)],
        _orientations(graph, 5, 6),
        start=None,
        preferences=PREFERENCES,
        head_only=False,
    )
    assert result.action == "route"
    assert result.edges[0] == (1, 2, 0)
    assert result.edges[-1] == (5, 6, 0)
    assert (4, 5, 0) in result.edges


def test_trace_extend_api_empty_path_selects_clicked() -> None:
    response = client.post(
        "/api/v1/routes/trace-extend?cityId=fixture",
        json={
            "selectedRoadIds": [],
            "clickedRoadId": "1:2:0",
            "profile": "road",
            "preferences": PREFERENCES_JSON,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "select"
    assert payload["roadIds"] == ["1:2:0"]
    assert payload["route"]["geometry"]["type"] == "LineString"
    assert payload["route"]["routeId"].startswith("rt_")


def test_trace_extend_api_skip_ahead_assembles_connected_path(monkeypatch) -> None:
    graph = _score(_named_network())
    monkeypatch.setattr(
        "app.services.routing.get_scored_graph",
        lambda _city_id, _profile: (graph, graph),
    )
    response = client.post(
        "/api/v1/routes/trace-extend?cityId=fixture",
        json={
            "selectedRoadIds": ["1:2:0"],
            "clickedRoadId": "3:4:0",
            "profile": "road",
            "preferences": PREFERENCES_JSON,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "same_road"
    assert payload["roadIds"] == ["1:2:0", "2:3:0", "3:4:0"]

    assembled = client.post(
        "/api/v1/routes/from-roads?cityId=fixture",
        json={"roadIds": payload["roadIds"], "profile": "road"},
    )
    assert assembled.status_code == 200


def test_trace_extend_api_expands_dropped_skip_click(monkeypatch) -> None:
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:32610"
    _add_node(graph, 10, lat=49.2775, lon=-123.2260, x=0.0)
    _add_node(graph, 20, lat=49.2776, lon=-123.2278, x=140.0)
    _add_node(graph, 30, lat=49.2783, lon=-123.2458, x=1500.0)
    marine = {
        "highway": "tertiary",
        "length_m": 140.0,
        "name": "Northwest Marine Drive",
    }
    _add_bidirectional(graph, 10, 20, **marine)
    _add_bidirectional(graph, 20, 30, **{**marine, "length_m": 1360.0})
    scored = _score(graph)
    monkeypatch.setattr(
        "app.services.routing.get_scored_graph",
        lambda _city_id, _profile: (scored, scored),
    )

    response = client.post(
        "/api/v1/routes/trace-extend?cityId=fixture",
        json={
            "selectedRoadIds": [],
            "clickedRoadId": "10:30:0",
            "profile": "road",
            "preferences": PREFERENCES_JSON,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["roadIds"][0] in {"10:20:0", "20:10:0"}


def test_from_roads_still_rejects_disconnected_skip() -> None:
    response = client.post(
        "/api/v1/routes/from-roads?cityId=fixture",
        json={"roadIds": ["1:2:0", "3:4:0"], "profile": "road"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_trace_extend_api_start_snaps_to_fixture_network() -> None:
    graph = _score(build_tiny_graph())
    start = graph.nodes[1]
    response = client.post(
        "/api/v1/routes/trace-extend?cityId=fixture",
        json={
            "selectedRoadIds": [],
            "clickedRoadId": "2:3:0",
            "start": {"lat": start["lat"], "lon": start["lon"]},
            "profile": "road",
            "preferences": PREFERENCES_JSON,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["roadIds"][0] == make_road_id(1, 2, 0)
    assert payload["roadIds"][-1] in {"2:3:0", "3:2:0"}
    assert payload["action"] in {"route", "select"}
