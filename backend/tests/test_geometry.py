from __future__ import annotations

import networkx as nx
from app.graph.fixture import build_tiny_graph
from app.graph.geometry import edge_to_wgs84_coordinates
from app.routing.metrics import path_to_coordinates
from shapely.geometry import LineString


def test_fixture_edge_fallback_coordinates() -> None:
    graph = build_tiny_graph()
    edge_data = graph.get_edge_data(1, 2, 0)
    coords = edge_to_wgs84_coordinates(graph, 1, 2, edge_data)

    assert len(coords) == 2
    assert coords[0] == [-123.12, 49.28]
    assert coords[1] == [-123.11, 49.281]


def test_curved_geometry_unprojection() -> None:
    graph = nx.MultiDiGraph()
    # EPSG:32610 is UTM Zone 10N (Vancouver / BC area)
    graph.graph["crs"] = "EPSG:32610"

    # Vancouver UTM coordinates roughly at (491400, 5458900)
    graph.add_node(1, lat=49.2827, lon=-123.1207, x=491217.0, y=5458872.0)
    graph.add_node(2, lat=49.2850, lon=-123.1150, x=491632.0, y=5459128.0)

    # Add intermediate curved points in UTM projection
    curved_linestring = LineString(
        [
            (491217.0, 5458872.0),
            (491400.0, 5459000.0),
            (491500.0, 5459050.0),
            (491632.0, 5459128.0),
        ]
    )
    edge_data = {"geometry": curved_linestring, "length_m": 500.0}
    graph.add_edge(1, 2, key=0, **edge_data)

    coords = edge_to_wgs84_coordinates(graph, 1, 2, edge_data)

    # Should have 4 intermediate points
    assert len(coords) == 4
    # First point should match node 1 approx WGS84
    assert abs(coords[0][0] - (-123.1207)) < 0.001
    assert abs(coords[0][1] - 49.2827) < 0.001
    # Last point should match node 2 approx WGS84
    assert abs(coords[-1][0] - (-123.1150)) < 0.001
    assert abs(coords[-1][1] - 49.2850) < 0.001


def test_path_to_coordinates_chains_curved_segments() -> None:
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:32610"
    graph.add_node(1, lat=49.28, lon=-123.12)
    graph.add_node(2, lat=49.29, lon=-123.11)
    graph.add_node(3, lat=49.30, lon=-123.10)

    # Without geometry: node-to-node
    graph.add_edge(1, 2, key=0, length_m=100.0)
    graph.add_edge(2, 3, key=0, length_m=100.0)

    coords = path_to_coordinates(graph, [1, 2, 3])
    assert len(coords) == 3
    assert coords[0] == [-123.12, 49.28]
    assert coords[1] == [-123.11, 49.29]
    assert coords[2] == [-123.10, 49.30]
