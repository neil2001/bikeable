import networkx as nx

from app.features.apply import read_features_from_edge
from app.features.normalize import coerce_tag, normalize_highway_class

WALK_LINK_HIGHWAYS = {"path", "footway", "pedestrian", "steps"}


def create_bike_graph(
    graph: nx.MultiDiGraph,
    *,
    allow_walk_links: bool = False,
) -> nx.MultiDiGraph:
    """Return a copy containing cyclable edges, optionally walkable connectors."""
    bike_graph = graph.copy()
    removable: list[tuple[int, int, int]] = []
    for source, target, key, edge_data in bike_graph.edges(keys=True, data=True):
        if read_features_from_edge(edge_data).traversable:
            continue
        if allow_walk_links and _is_walk_link(edge_data):
            edge_data["walk_link"] = True
            continue
        removable.append((source, target, key))
    bike_graph.remove_edges_from(removable)
    return bike_graph


def _is_walk_link(edge_data: dict) -> bool:
    highway = normalize_highway_class(edge_data.get("highway"))
    if highway not in WALK_LINK_HIGHWAYS:
        return False
    if coerce_tag(edge_data.get("access")) == "private":
        return False
    return True
