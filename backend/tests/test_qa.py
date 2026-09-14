import networkx as nx
from app.graph.qa import analyze_graph


def _road(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    *,
    name: str,
    osmid: int,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> None:
    graph.add_node(source, x=x0, y=y0, lat=y0 / 111_000, lon=x0 / 85_000)
    graph.add_node(target, x=x1, y=y1, lat=y1 / 111_000, lon=x1 / 85_000)
    graph.add_edge(
        source,
        target,
        key=0,
        name=name,
        osmid=osmid,
        highway="residential",
        length_m=abs(y1 - y0) + abs(x1 - x0),
    )


def test_qa_detects_named_road_gap_and_broken_way_leaf() -> None:
    graph = nx.MultiDiGraph()
    _road(graph, 1, 2, name="Marine Drive", osmid=10, x0=0, y0=0, x1=0, y1=100)
    _road(graph, 2, 3, name="Marine Drive", osmid=10, x0=0, y0=100, x1=0, y1=200)
    _road(graph, 3, 4, name="Marine Drive", osmid=10, x0=0, y0=200, x1=0, y1=300)
    _road(graph, 10, 11, name="Marine Drive", osmid=11, x0=500, y0=0, x1=600, y1=0)
    _road(graph, 11, 12, name="Marine Drive", osmid=11, x0=600, y0=0, x1=700, y1=0)
    _road(graph, 20, 21, name="Side Street", osmid=20, x0=0, y0=500, x1=50, y1=500)

    report = analyze_graph(graph)
    assert report.node_count == 9
    assert report.weakly_connected_components == 3
    assert report.named_road_gaps[0].name == "Marine Drive"
    assert report.named_road_gaps[0].component_count == 2
    assert report.leaf_nodes > 0
    assert isinstance(report.broken_way_leaves, int)


def test_qa_connected_named_road_has_no_gap() -> None:
    graph = nx.MultiDiGraph()
    _road(graph, 1, 2, name="Broadway", osmid=1, x0=0, y0=0, x1=100, y1=0)
    _road(graph, 2, 3, name="Broadway", osmid=1, x0=100, y0=0, x1=200, y1=0)
    _road(graph, 3, 4, name="Broadway", osmid=1, x0=200, y0=0, x1=300, y1=0)
    _road(graph, 4, 5, name="Broadway", osmid=1, x0=300, y0=0, x1=400, y1=0)
    report = analyze_graph(graph)
    assert report.named_road_gaps == []
    assert report.weakly_connected_components == 1
