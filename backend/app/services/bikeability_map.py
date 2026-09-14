from typing import Any

import networkx as nx
from app.features.apply import read_features_from_edge
from app.graph.geometry import edge_to_overlay_coordinates
from app.routing.ids import json_osmid, make_road_id

OverlayGeoJSON = dict[str, Any]


def _osmid_key(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, list):
        return tuple(value)
    return value


def _is_traversable(edge_data: dict[str, Any]) -> bool:
    return read_features_from_edge(edge_data).traversable


def _find_reverse_edge(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    edge_data: dict[str, Any],
    consumed: set[tuple[int, int, int]],
) -> tuple[int, int, int, dict[str, Any]] | None:
    if source == target or not graph.has_edge(target, source):
        return None

    osmid = _osmid_key(edge_data.get("osmid"))
    fallback: tuple[int, int, int, dict[str, Any]] | None = None
    for reverse_key, reverse_data in graph[target][source].items():
        edge_id = (target, source, reverse_key)
        if edge_id in consumed or not _is_traversable(reverse_data):
            continue
        reverse_osmid = _osmid_key(reverse_data.get("osmid"))
        if osmid is not None and reverse_osmid == osmid:
            return (*edge_id, reverse_data)
        if fallback is None:
            fallback = (*edge_id, reverse_data)
    return fallback


def _choose_canonical(
    left: tuple[int, int, int, dict[str, Any]],
    right: tuple[int, int, int, dict[str, Any]] | None,
) -> tuple[int, int, int, dict[str, Any]]:
    if right is None:
        return left
    left_score = float(left[3].get("bikeability", 0.0))
    right_score = float(right[3].get("bikeability", 0.0))
    if right_score > left_score:
        return right
    if left_score > right_score:
        return left
    return left if left[:3] <= right[:3] else right


def graph_to_bikeability_geojson(
    graph: nx.MultiDiGraph,
    *,
    city_id: str,
    score_version: str,
) -> OverlayGeoJSON:
    """Build a compact GeoJSON overlay: traversable, undirected, simplified."""
    consumed: set[tuple[int, int, int]] = set()
    features: list[dict[str, Any]] = []

    for source, target, key, edge_data in graph.edges(keys=True, data=True):
        edge_id = (source, target, key)
        if edge_id in consumed:
            continue
        consumed.add(edge_id)
        if not _is_traversable(edge_data):
            continue

        reverse = _find_reverse_edge(graph, source, target, edge_data, consumed)
        if reverse is not None:
            consumed.add(reverse[:3])

        chosen_source, chosen_target, chosen_key, chosen_data = _choose_canonical(
            (source, target, key, edge_data),
            reverse,
        )
        coordinates = edge_to_overlay_coordinates(
            graph,
            chosen_source,
            chosen_target,
            chosen_data,
        )
        if len(coordinates) < 2:
            continue

        osmid = json_osmid(chosen_data.get("osmid"))
        properties = {
            "roadId": make_road_id(chosen_source, chosen_target, chosen_key),
            "bikeability": round(float(chosen_data.get("bikeability", 0.0)), 2),
        }
        if osmid is not None:
            properties["osmid"] = osmid
        feature: dict[str, Any] = {
            "type": "Feature",
            "properties": properties,
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates,
            },
        }
        if isinstance(osmid, int):
            feature["id"] = osmid
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "cityId": city_id,
        "scoreVersion": score_version,
        "features": features,
    }
