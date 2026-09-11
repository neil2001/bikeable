from __future__ import annotations

from functools import lru_cache
from typing import Any

import networkx as nx
from pyproj import Transformer
from shapely.ops import transform

OVERLAY_SIMPLIFY_M = 10.0
OVERLAY_COORD_DECIMALS = 5


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


def _round_and_dedupe(
    coords: list[list[float]],
    *,
    decimals: int = OVERLAY_COORD_DECIMALS,
) -> list[list[float]]:
    if not coords:
        return []
    rounded = [
        [round(point[0], decimals), round(point[1], decimals)] for point in coords
    ]
    deduped = [rounded[0]]
    for point in rounded[1:]:
        if point != deduped[-1]:
            deduped.append(point)
    if len(deduped) >= 2:
        return deduped
    if len(rounded) >= 2:
        return [rounded[0], rounded[-1]]
    return rounded


def edge_to_overlay_coordinates(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    edge_data: dict[str, Any],
    *,
    simplify_m: float = OVERLAY_SIMPLIFY_M,
    decimals: int = OVERLAY_COORD_DECIMALS,
) -> list[list[float]]:
    """WGS84 overlay coords: simplify in metres, then round and drop duplicates."""
    geom = edge_data.get("geometry")
    crs = graph.graph.get("crs")
    overlay_data = edge_data
    if (
        geom is not None
        and hasattr(geom, "simplify")
        and crs
        and "4326" not in str(crs)
        and simplify_m > 0
    ):
        simplified = geom.simplify(simplify_m, preserve_topology=False)
        if simplified is not None and getattr(simplified, "is_empty", False) is False:
            overlay_data = {**edge_data, "geometry": simplified}

    return _round_and_dedupe(
        edge_to_wgs84_coordinates(graph, source, target, overlay_data),
        decimals=decimals,
    )
