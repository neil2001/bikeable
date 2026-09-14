import pytest
from app.graph.fixture import build_tiny_graph
from app.models.common import Coordinate
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
