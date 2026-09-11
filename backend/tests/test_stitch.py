import networkx as nx
from app.graph.stitch import stitch_graphs


def _add_edge(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    *,
    osmid: int,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    **tags: object,
) -> None:
    graph.add_node(source, x=x0, y=y0, lat=y0 / 111_000, lon=x0 / 85_000)
    graph.add_node(target, x=x1, y=y1, lat=y1 / 111_000, lon=x1 / 85_000)
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    graph.add_edge(
        source,
        target,
        key=0,
        osmid=osmid,
        length=length,
        length_m=length,
        highway="residential",
        **tags,
    )


def test_stitch_joins_shared_osm_node_ids() -> None:
    left = nx.MultiDiGraph()
    _add_edge(left, 1, 2, osmid=100, x0=0, y0=0, x1=100, y1=0)

    right = nx.MultiDiGraph()
    _add_edge(right, 2, 3, osmid=100, x0=100, y0=0, x1=200, y1=0)

    stitched = stitch_graphs([left, right])
    assert stitched.has_edge(1, 3)
    assert nx.is_weakly_connected(stitched)
    assert stitched.number_of_edges() == 1


def test_stitch_snaps_clipped_endpoints_with_shared_osmid() -> None:
    left = nx.MultiDiGraph()
    _add_edge(left, 1, 1001, osmid=200, x0=0, y0=0, x1=98, y1=0)

    right = nx.MultiDiGraph()
    _add_edge(right, 1002, 2, osmid=200, x0=100, y0=0, x1=200, y1=0)

    stitched = stitch_graphs([left, right], snap_tolerance_m=5.0)
    assert 1001 not in stitched
    assert 1002 not in stitched
    assert nx.is_weakly_connected(stitched)
    assert stitched.number_of_edges() == 1


def test_stitch_does_not_snap_parallel_roads_with_different_osmids() -> None:
    eastbound = nx.MultiDiGraph()
    _add_edge(eastbound, 1, 2, osmid=300, x0=0, y0=0, x1=100, y1=0)

    northbound = nx.MultiDiGraph()
    _add_edge(northbound, 3, 4, osmid=400, x0=2, y0=0, x1=2, y1=100)

    stitched = stitch_graphs([eastbound, northbound], snap_tolerance_m=5.0)
    assert stitched.number_of_nodes() == 4
    assert stitched.number_of_edges() == 2


def test_stitch_dedupes_overlap_edges_and_merges_tags() -> None:
    graph = nx.MultiDiGraph()
    _add_edge(graph, 1, 2, osmid=500, x0=0, y0=0, x1=100, y1=0)
    graph.add_edge(
        1,
        2,
        key=1,
        osmid=500,
        length=100,
        length_m=100,
        highway="residential",
        **{"cycleway:right": "lane"},
    )

    stitched = stitch_graphs([graph])
    assert stitched.number_of_edges() == 1
    edge = next(iter(stitched[1][2].values()))
    assert edge["cycleway:right"] == "lane"
