import networkx as nx
from app.config import settings
from app.graph.loader import GraphPipelineError, load_city_graph
from app.graph.registry import get_city_definition
from app.graph.store import processed_graph_paths
from app.scoring.bike_graph import create_bike_graph
from app.scoring.score import score_graph


class CityGraphUnavailableError(Exception):
    def __init__(self, city_id: str, reason: str) -> None:
        super().__init__(reason)
        self.city_id = city_id
        self.reason = reason


def city_graph_is_available(city_id: str) -> bool:
    city = get_city_definition(city_id)
    if city.is_fixture:
        return True
    paths = processed_graph_paths(settings.processed_data_dir, city_id)
    return paths.graphml.exists()


def get_scored_graph(
    city_id: str,
    profile_id: str,
) -> tuple[nx.MultiDiGraph, nx.MultiDiGraph]:
    try:
        get_city_definition(city_id)
    except KeyError as exc:
        raise CityGraphUnavailableError(city_id, str(exc)) from exc

    if not city_graph_is_available(city_id):
        raise CityGraphUnavailableError(
            city_id,
            f"Processed graph for '{city_id}' has not been built yet.",
        )

    try:
        graph = load_city_graph(city_id)
    except (FileNotFoundError, GraphPipelineError) as exc:
        raise CityGraphUnavailableError(city_id, str(exc)) from exc

    scored = score_graph(graph, profile_id)
    return scored, create_bike_graph(scored)
