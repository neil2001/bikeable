import networkx as nx

from app.features.apply import read_features_from_edge


def create_bike_graph(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Return a copy containing only edges marked traversable for bicycles."""
    bike_graph = graph.copy()
    removable = [
        (source, target, key)
        for source, target, key, edge_data in bike_graph.edges(keys=True, data=True)
        if not read_features_from_edge(edge_data).traversable
    ]
    bike_graph.remove_edges_from(removable)
    return bike_graph
