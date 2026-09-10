import math

import networkx as nx
from app.models.common import Coordinate


def nearest_node(graph: nx.MultiDiGraph, point: Coordinate) -> int:
    best_node: int | None = None
    best_distance = float("inf")

    for node_id, node_data in graph.nodes(data=True):
        distance = _haversine_m(
            point.lat,
            point.lon,
            float(node_data["lat"]),
            float(node_data["lon"]),
        )
        if distance < best_distance:
            best_distance = distance
            best_node = int(node_id)

    if best_node is None:
        msg = "Graph has no nodes to snap against."
        raise ValueError(msg)
    return best_node


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))
