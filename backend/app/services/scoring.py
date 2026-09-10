import networkx as nx
from app.scoring.bike_graph import create_bike_graph
from app.scoring.config import get_profile
from app.scoring.score import score_graph, score_road

__all__ = [
    "create_bike_graph",
    "get_profile",
    "score_graph",
    "score_road",
]


def get_scored_city_graph(
    city_graph: nx.MultiDiGraph, profile_id: str
) -> nx.MultiDiGraph:
    return score_graph(city_graph, profile_id)
