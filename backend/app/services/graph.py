from app.graph.loader import build_city_graph, load_city_graph

__all__ = ["build_city_graph", "load_city_graph"]


def get_city_graph(city_id: str):
    return load_city_graph(city_id)
