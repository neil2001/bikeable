import networkx as nx
import pytest
from app.graph.fixture import build_tiny_graph
from app.graph.ingest import normalize_graph
from app.models.common import Coordinate
from app.routing.index import attach_routing_index
from app.routing.nearest import DEFAULT_MAX_SNAP_M, nearest_edge_snap, nearest_node


def test_nearest_node_snaps_on_network() -> None:
    graph = build_tiny_graph()
    node = nearest_node(graph, Coordinate(lat=49.2800, lon=-123.1200))
    assert node == 1


def test_nearest_edge_prefers_corridor_not_far_node() -> None:
    graph = build_tiny_graph()
    node, distance = nearest_edge_snap(
        graph, Coordinate(lat=49.2805, lon=-123.1150)
    )
    assert node in {1, 2}
    assert distance < 200


def test_nearest_node_rejects_points_far_from_network() -> None:
    graph = build_tiny_graph()
    with pytest.raises(ValueError, match="street network"):
        nearest_node(
            graph,
            Coordinate(lat=50.0, lon=-124.0),
            max_distance_m=DEFAULT_MAX_SNAP_M,
        )


def test_indexed_snap_prefers_long_corridor_over_nearby_node_cluster() -> None:
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:32610"
    graph.add_node(1, lat=49.2800, lon=-123.1200, x=0.0, y=0.0)
    graph.add_node(2, lat=49.2810, lon=-123.1100, x=1000.0, y=0.0)
    graph.add_edge(1, 2, key=0, highway="residential", length_m=1000.0, osmid=1)
    graph.add_edge(2, 1, key=0, highway="residential", length_m=1000.0, osmid=1)
    graph.add_node(3, lat=49.2805, lon=-123.1150, x=500.0, y=80.0)
    graph.add_node(4, lat=49.2806, lon=-123.1150, x=505.0, y=85.0)
    graph.add_edge(3, 4, key=0, highway="residential", length_m=10.0, osmid=2)
    graph = normalize_graph(graph)
    attach_routing_index(graph)

    node = nearest_node(
        graph,
        Coordinate(lat=49.28025, lon=-123.1150),
    )
    assert node in {1, 2}
    assert node != 3


def test_nearest_node_rejects_far_point_with_routing_index() -> None:
    graph = attach_routing_index(build_tiny_graph())
    with pytest.raises(ValueError, match="street network"):
        nearest_node(
            graph,
            Coordinate(lat=50.0, lon=-124.0),
            max_distance_m=DEFAULT_MAX_SNAP_M,
        )
