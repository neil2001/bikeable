from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import networkx as nx
import osmnx as ox

from app.features.normalize import coerce_tag, normalize_highway_class
from app.graph.extract import OsmExtractError, has_usable_extract, resolve_osm_xml
from app.graph.registry import CityDefinition
from app.graph.types import BBox

EXTRA_WAY_TAGS = (
    "bicycle",
    "cycleway",
    "cycleway:left",
    "cycleway:right",
    "cycleway:both",
    "surface",
    "smoothness",
    "lcn",
    "rcn",
    "ncn",
    "incline",
    "foot",
    "segregated",
    "motor_vehicle",
)

EXCLUDED_HIGHWAYS = {
    "abandoned",
    "construction",
    "planned",
    "proposed",
    "platform",
    "raceway",
    "razed",
    "bus_guideway",
    "elevator",
    "escalator",
    "corridor",
    "motorway",
    "motorway_link",
}


def configure_osmnx_tags() -> None:
    """Keep cycling and surface tags that scoring needs."""
    ox.settings.useful_tags_way = list(
        {*ox.settings.useful_tags_way, *EXTRA_WAY_TAGS},
    )


CUSTOM_FILTER = (
    '["highway"]["area"!~"yes"]'
    '["highway"!~"abandoned|construction|planned|proposed|platform|raceway|'
    'razed|bus_guideway|elevator|escalator|corridor|motorway|motorway_link"]'
    '["bicycle"!~"no"]'
    '["access"!~"private"]'
)


def build_osm_graph(
    city: CityDefinition,
    *,
    osm_path: Path | None = None,
) -> nx.MultiDiGraph:
    """Build a cyclable NetworkX graph from one OSM extract or one bbox query."""
    if osm_path is not None or has_usable_extract(city):
        try:
            xml_path = resolve_osm_xml(city, osm_path=osm_path)
            return graph_from_osm_xml(xml_path, bbox=city.osm_bbox)
        except (OsmExtractError, subprocess.CalledProcessError):
            if osm_path is not None or city.osm_bbox is None:
                raise
    if city.osm_bbox is None:
        msg = f"City '{city.city_id}' has no OSM bbox or extract path."
        raise ValueError(msg)
    return graph_from_bbox(city)


def graph_from_bbox(city: CityDefinition) -> nx.MultiDiGraph:
    if city.osm_bbox is None:
        msg = f"City '{city.city_id}' has no OSM bbox."
        raise ValueError(msg)
    configure_osmnx_tags()
    ox.settings.requests_timeout = 300
    graph = ox.graph_from_bbox(
        city.osm_bbox,
        custom_filter=CUSTOM_FILTER,
        simplify=True,
        retain_all=False,
        truncate_by_edge=True,
    )
    return _prepare_downloaded_graph(graph, bbox=city.osm_bbox)


def graph_from_osm_xml(
    xml_path: Path,
    *,
    bbox: BBox | None = None,
) -> nx.MultiDiGraph:
    configure_osmnx_tags()
    graph = ox.graph_from_xml(xml_path, simplify=True, retain_all=False)
    return _prepare_downloaded_graph(graph, bbox=bbox, osm_xml=xml_path)


def _prepare_downloaded_graph(
    graph: nx.MultiDiGraph,
    *,
    bbox: BBox | None,
    osm_xml: Path | None = None,
) -> nx.MultiDiGraph:
    graph = _drop_excluded_edges(graph)
    graph = ensure_wgs84_coordinates(graph)
    if bbox is not None:
        graph = annotate_park_edges(graph, bbox, osm_xml=osm_xml)
    if graph.number_of_nodes() == 0:
        return normalize_graph(graph)
    graph = ox.project_graph(graph)
    return normalize_graph(graph)


def keep_ingest_edge(edge_data: dict[str, Any]) -> bool:
    highway = normalize_highway_class(edge_data.get("highway"))
    if highway is None or highway in EXCLUDED_HIGHWAYS:
        return False
    if coerce_tag(edge_data.get("bicycle")) == "no":
        return False
    if coerce_tag(edge_data.get("access")) == "private":
        return False
    return True


def _drop_excluded_edges(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    removable = [
        (source, target, key)
        for source, target, key, edge_data in graph.edges(keys=True, data=True)
        if not keep_ingest_edge(edge_data)
    ]
    graph.remove_edges_from(removable)
    graph.remove_nodes_from(list(nx.isolates(graph)))
    return graph


def annotate_park_edges(
    graph: nx.MultiDiGraph,
    bbox: BBox,
    *,
    osm_xml: Path | None = None,
) -> nx.MultiDiGraph:
    """Mark edges whose midpoint is within ~40 m of a park or forest."""
    parks = _load_park_geometries(bbox, osm_xml=osm_xml)
    if parks is None:
        return graph

    from shapely.geometry import Point
    from shapely.ops import unary_union

    geoms = [geom for geom in parks if geom is not None]
    if not geoms:
        return graph
    # ~40 m in degrees at Vancouver latitude
    park_area = unary_union(geoms).buffer(0.00036)
    for _source, _target, _key, edge_data in graph.edges(keys=True, data=True):
        source_node = graph.nodes[_source]
        target_node = graph.nodes[_target]
        mid = Point(
            (float(source_node["lon"]) + float(target_node["lon"])) / 2,
            (float(source_node["lat"]) + float(target_node["lat"])) / 2,
        )
        edge_data["in_park"] = bool(park_area.intersects(mid))
    return graph


def _load_park_geometries(
    bbox: BBox,
    *,
    osm_xml: Path | None,
):
    tags = {"leisure": "park", "landuse": "forest"}
    if osm_xml is not None:
        try:
            features = ox.features_from_xml(osm_xml, tags)
            if features is not None and not features.empty:
                return features.geometry.dropna().tolist()
        except Exception:
            pass
    try:
        features = ox.features_from_bbox(bbox, tags=tags)
    except Exception:
        return None
    if features is None or features.empty:
        return None
    return features.geometry.dropna().tolist()


def ensure_wgs84_coordinates(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Copy OSMnx x/y coordinates into lat/lon before graph projection."""
    for _node_id, node_data in graph.nodes(data=True):
        if "lat" in node_data and "lon" in node_data:
            continue
        if "x" not in node_data or "y" not in node_data:
            msg = "Graph node is missing WGS84 coordinates."
            raise ValueError(msg)
        node_data["lat"] = float(node_data["y"])
        node_data["lon"] = float(node_data["x"])
    return graph


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


__all__ = [
    "EXTRA_WAY_TAGS",
    "OsmExtractError",
    "annotate_park_edges",
    "build_osm_graph",
    "configure_osmnx_tags",
    "ensure_wgs84_coordinates",
    "graph_from_bbox",
    "graph_from_bbox",
    "graph_from_osm_xml",
    "keep_ingest_edge",
    "normalize_graph",
]
