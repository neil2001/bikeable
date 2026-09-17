import networkx as nx

from app.features.apply import apply_features_to_graph
from app.models.common import Coordinate
from app.routing.nearest import nearest_node
from app.scoring.bike_graph import create_bike_graph


def _add_node(graph: nx.MultiDiGraph, node_id: int, lat: float, lon: float) -> None:
    graph.add_node(node_id, lat=lat, lon=lon, x=lon, y=lat)


def test_necessary_connector_footway_is_walk_link() -> None:
    graph = nx.MultiDiGraph()
    for node_id, lat, lon in (
        (1, 49.0, -123.0),
        (2, 49.001, -123.0),
        (3, 49.002, -123.0),
        (4, 49.003, -123.0),
    ):
        _add_node(graph, node_id, lat, lon)
    graph.add_edge(1, 2, key=0, highway="cycleway", bicycle="designated", length_m=100.0)
    graph.add_edge(3, 4, key=0, highway="cycleway", bicycle="designated", length_m=100.0)
    graph.add_edge(1, 4, key=0, highway="residential", length_m=5000.0)
    graph.add_edge(2, 3, key=0, highway="footway", length_m=30.0)

    apply_features_to_graph(graph)
    bike_graph = create_bike_graph(graph, allow_walk_links=True)

    assert bike_graph.has_edge(2, 3, 0)
    assert bike_graph[2][3][0]["walk_link"] is True
    assert bike_graph[2][3][0]["necessary_connector"] is True


def test_parallel_footway_with_short_detour_is_dropped() -> None:
    graph = nx.MultiDiGraph()
    _add_node(graph, 1, 49.0, -123.0)
    _add_node(graph, 2, 49.001, -123.0)
    graph.add_edge(1, 2, key=0, highway="residential", length_m=50.0)
    graph.add_edge(2, 1, key=0, highway="residential", length_m=50.0)
    graph.add_edge(1, 2, key=1, highway="footway", length_m=40.0)

    apply_features_to_graph(graph)
    bike_graph = create_bike_graph(graph, allow_walk_links=True)

    assert not bike_graph.has_edge(1, 2, 1)


def test_vancouver_west_georgia_to_park_royal_crosses_lions_gate() -> None:
    import pytest
    from app.config import settings
    from app.graph.store import graph_cache_exists, load_processed_graph, processed_graph_paths

    paths = processed_graph_paths(settings.processed_data_dir, "vancouver")
    if not graph_cache_exists(paths):
        pytest.skip("requires processed Vancouver city graph")

    graph = apply_features_to_graph(load_processed_graph(paths))
    bike_graph = create_bike_graph(graph, allow_walk_links=True)

    start = Coordinate(lat=49.28345, lon=-123.11960)
    end = Coordinate(lat=49.32401, lon=-123.1375)
    start_node = nearest_node(bike_graph, start)
    end_node = nearest_node(bike_graph, end)

    path = nx.shortest_path(bike_graph, start_node, end_node, weight="length_m")
    total_m = 0.0
    uses_lions_gate = False
    for source, target in zip(path, path[1:]):
        edge_data = min(
            bike_graph[source][target].values(),
            key=lambda data: float(data.get("length_m") or data.get("length") or 0.0),
        )
        total_m += float(edge_data.get("length_m") or edge_data.get("length") or 0.0)
        name = edge_data.get("name") or ""
        if isinstance(name, list):
            name = name[0] if name else ""
        if "lions gate" in str(name).lower():
            uses_lions_gate = True

    assert 4500 <= total_m <= 8000
    assert uses_lions_gate
