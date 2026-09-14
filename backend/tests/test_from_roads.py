import networkx as nx
from app.features.apply import apply_features_to_graph
from app.graph.fixture import build_tiny_graph
from app.graph.geometry import edge_to_wgs84_coordinates
from app.main import app
from app.routing.metrics import edges_to_coordinates
from app.scoring.score import score_graph
from fastapi.testclient import TestClient
from shapely.geometry import LineString

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


def test_from_roads_skips_elevation_lookup(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("sample_path_elevations should not run for from-roads")

    monkeypatch.setattr(
        "app.services.routing.sample_path_elevations",
        fail_if_called,
    )
    response = client.post(
        "/api/v1/routes/from-roads?cityId=fixture",
        json={"roadIds": ["1:2:0"], "profile": "road"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["elevationGainM"] == 0.0
    assert all(sample["elevationM"] is None for sample in payload["profile"])


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


def test_from_roads_expands_dropped_skip_edge() -> None:
    from app.services.routing import _edges_from_road_ids

    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:32610"
    graph.add_node(10, lat=49.2775, lon=-123.2260, x=0.0, y=0.0)
    graph.add_node(20, lat=49.2776, lon=-123.2278, x=0.0, y=140.0)
    graph.add_node(30, lat=49.2783, lon=-123.2458, x=0.0, y=1500.0)
    graph.add_edge(
        10, 20, key=0, highway="tertiary", length_m=140.0, name="Northwest Marine Drive"
    )
    graph.add_edge(
        20,
        30,
        key=0,
        highway="tertiary",
        length_m=1360.0,
        name="Northwest Marine Drive",
    )
    scored = score_graph(apply_features_to_graph(graph), "road")

    edges = _edges_from_road_ids(scored, ["10:30:0"])
    assert edges == [(10, 20, 0), (20, 30, 0)]


def test_from_roads_rejects_invalid_road_id() -> None:
    response = client.post(
        "/api/v1/routes/from-roads?cityId=fixture",
        json={"roadIds": ["not-a-road"], "profile": "road"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def _parallel_edge_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:32610"
    graph.add_node(1, lat=49.2800, lon=-123.1200, x=0.0, y=0.0)
    graph.add_node(2, lat=49.2810, lon=-123.1100, x=1000.0, y=0.0)

    direct = LineString([(0.0, 0.0), (1000.0, 0.0)])
    detour = LineString([(0.0, 0.0), (500.0, 200.0), (1000.0, 0.0)])
    graph.add_edge(
        1,
        2,
        key=0,
        highway="residential",
        length_m=1000.0,
        geometry=direct,
        osmid=100,
    )
    graph.add_edge(
        1,
        2,
        key=1,
        highway="residential",
        length_m=1100.0,
        geometry=detour,
        osmid=101,
    )
    return score_graph(apply_features_to_graph(graph), "road")


def test_from_roads_uses_parallel_edge_geometry_for_requested_key(monkeypatch) -> None:
    scored = _parallel_edge_graph()
    coords_key_0 = edges_to_coordinates(scored, [(1, 2, 0)])
    coords_key_1 = edges_to_coordinates(scored, [(1, 2, 1)])
    assert len(coords_key_0) == 2
    assert len(coords_key_1) == 3
    assert coords_key_0 != coords_key_1

    monkeypatch.setattr(
        "app.services.routing.get_scored_graph",
        lambda _city_id, _profile: (scored, scored),
    )

    response = client.post(
        "/api/v1/routes/from-roads?cityId=fixture",
        json={"roadIds": ["1:2:1"], "profile": "road"},
    )
    assert response.status_code == 200
    assert response.json()["geometry"]["coordinates"] == coords_key_1


def test_from_roads_resolves_reverse_orientation_with_matching_osmid() -> None:
    graph = apply_features_to_graph(build_tiny_graph())
    scored = score_graph(graph, "road")
    edge_data = scored.get_edge_data(1, 2, 0)
    assert edge_data is not None
    forward = edge_to_wgs84_coordinates(scored, 1, 2, edge_data)

    response = client.post(
        "/api/v1/routes/from-roads?cityId=fixture",
        json={"roadIds": ["2:1:0"], "profile": "road"},
    )
    assert response.status_code == 200
    reverse = response.json()["geometry"]["coordinates"]
    assert reverse[0] == forward[-1]
    assert reverse[-1] == forward[0]


def test_from_roads_rejects_ambiguous_parallel_edges_without_key_match() -> None:
    from app.routing.point_to_point import RoutingError
    from app.services.routing import _edges_from_road_ids

    scored = _parallel_edge_graph()
    try:
        _edges_from_road_ids(scored, ["1:2:99"])
    except RoutingError as exc:
        assert exc.code == "INVALID_REQUEST"
        assert "ambiguous" in exc.message.lower()
    else:
        raise AssertionError("expected ambiguous road resolution to fail")


def test_vancouver_marine_skip_id_expands_to_connector_chain() -> None:
    import pytest
    from app.config import settings
    from app.graph.store import (
        graph_cache_exists,
        load_processed_graph,
        processed_graph_paths,
    )
    from app.routing.resolve import resolve_road_edges

    paths = processed_graph_paths(settings.processed_data_dir, "vancouver")
    if not graph_cache_exists(paths):
        pytest.skip("requires processed Vancouver city graph")

    graph = load_processed_graph(paths)
    edges = resolve_road_edges(graph, 1315815911, 1315815979, 0)
    assert edges[0][0] == 1315815911
    assert edges[0][1] == 1315815946
    assert edges[-1][1] == 1315815979
    assert not graph.has_edge(1315815911, 1315815979)
