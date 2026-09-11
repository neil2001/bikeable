from __future__ import annotations

from typing import Any

import networkx as nx

from app.config import settings
from app.elevation.null_provider import sample_elevations
from app.elevation.open_meteo import lookup_elevations


def sample_path_elevations(
    graph: nx.MultiDiGraph,
    path: list[Any],
) -> list[float | None]:
    """Sample elevation in meters for each node on a routed path."""
    if not path:
        return []
    if settings.elevation_provider != "open_meteo":
        return sample_elevations(len(path))

    coordinates: list[tuple[float, float]] = []
    for node_id in path:
        coordinate = _node_coordinate(graph, node_id)
        if coordinate is None:
            return sample_elevations(len(path))
        coordinates.append(coordinate)

    try:
        elevations = lookup_elevations(
            coordinates,
            api_url=settings.elevation_api_url,
        )
    except OSError:
        return sample_elevations(len(path))

    if len(elevations) != len(path) or all(value is None for value in elevations):
        return sample_elevations(len(path))
    return elevations


def _node_coordinate(
    graph: nx.MultiDiGraph,
    node_id: Any,
) -> tuple[float, float] | None:
    node = graph.nodes[node_id]
    try:
        return (float(node["lat"]), float(node["lon"]))
    except (KeyError, TypeError, ValueError):
        return None
