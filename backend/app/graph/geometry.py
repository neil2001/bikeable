from __future__ import annotations

from functools import lru_cache
from typing import Any

import networkx as nx
from pyproj import Transformer
from shapely.ops import transform


@lru_cache(maxsize=32)
def get_crs_transformer(crs: str) -> Transformer:
    """Cache CRS to WGS84 transformer."""
    return Transformer.from_crs(crs, "EPSG:4326", always_xy=True)


def edge_to_wgs84_coordinates(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    edge_data: dict[str, Any],
) -> list[list[float]]:
    """Convert an edge's geometry to WGS84 [lon, lat] coordinates."""
    source_node = graph.nodes[source]
    target_node = graph.nodes[target]
    fallback = [
        [float(source_node["lon"]), float(source_node["lat"])],
        [float(target_node["lon"]), float(target_node["lat"])],
    ]

    geom = edge_data.get("geometry")
    if geom is None:
        return fallback

    crs = graph.graph.get("crs")
    if not crs:
        if hasattr(geom, "coords"):
            return [[float(x), float(y)] for x, y in geom.coords]
        return fallback

    try:
        transformer = get_crs_transformer(str(crs))
        wgs_geom = transform(transformer.transform, geom)
        coords = [[float(x), float(y)] for x, y in wgs_geom.coords]
        if len(coords) >= 2:
            return coords
    except Exception:
        pass

    return fallback
