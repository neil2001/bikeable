import networkx as nx
import osmnx as ox


def download_city_graph(osm_place: str) -> nx.MultiDiGraph:
    """Download a drive network and prepare it for downstream processing."""
    graph = ox.graph_from_place(osm_place, network_type="drive", simplify=True)
    graph = ox.project_graph(graph)
    graph = ox.add_edge_lengths(graph)
    return normalize_graph(graph)


def normalize_graph(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Ensure routable edges and nodes expose the attributes later layers expect."""
    for _node_id, node_data in graph.nodes(data=True):
        if "lat" not in node_data or "lon" not in node_data:
            msg = "Graph node is missing lat/lon coordinates."
            raise ValueError(msg)

    for _source, _target, _key, edge_data in graph.edges(keys=True, data=True):
        length_m = edge_data.get("length_m")
        if length_m is None:
            raw_length = edge_data.get("length")
            if raw_length is None:
                msg = "Graph edge is missing length."
                raise ValueError(msg)
            edge_data["length_m"] = float(raw_length)

    return graph
