import networkx as nx
import osmnx as ox

from app.graph.registry import CityDefinition, SectionDefinition

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


def configure_osmnx_tags() -> None:
    """Keep cycling and surface tags that scoring needs."""
    ox.settings.useful_tags_way = list(
        {*ox.settings.useful_tags_way, *EXTRA_WAY_TAGS},
    )


def download_section_graph(section: SectionDefinition) -> nx.MultiDiGraph:
    """Download a single metro section (drive ∪ bike) for later stitching."""
    configure_osmnx_tags()
    drive = ox.graph_from_bbox(
        section.osm_bbox,
        network_type="drive",
        simplify=True,
        truncate_by_edge=True,
    )
    bike = ox.graph_from_bbox(
        section.osm_bbox,
        network_type="bike",
        simplify=True,
        truncate_by_edge=True,
    )
    graph = merge_graphs(drive, bike)
    graph = ensure_wgs84_coordinates(graph)
    graph = annotate_park_edges(graph, section.osm_bbox)
    graph = ox.project_graph(graph)
    return normalize_graph(graph)


def download_city_graph(city: CityDefinition) -> nx.MultiDiGraph:
    """Download a cyclable network (drive ∪ bike) and prepare it for scoring."""
    configure_osmnx_tags()
    if city.osm_bbox is not None:
        drive = ox.graph_from_bbox(
            city.osm_bbox,
            network_type="drive",
            simplify=True,
            truncate_by_edge=True,
        )
        bike = ox.graph_from_bbox(
            city.osm_bbox,
            network_type="bike",
            simplify=True,
            truncate_by_edge=True,
        )
        graph = merge_graphs(drive, bike)
        graph = ensure_wgs84_coordinates(graph)
        graph = annotate_park_edges(graph, city.osm_bbox)
    elif city.osm_place is not None:
        drive = ox.graph_from_place(city.osm_place, network_type="drive", simplify=True)
        bike = ox.graph_from_place(city.osm_place, network_type="bike", simplify=True)
        graph = merge_graphs(drive, bike)
        graph = ensure_wgs84_coordinates(graph)
    else:
        msg = f"City '{city.city_id}' has no OSM bbox or place query."
        raise ValueError(msg)

    graph = ox.project_graph(graph)
    return normalize_graph(graph)


def _osmid_key(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, list):
        return tuple(value)
    return value


def merge_graphs(drive: nx.MultiDiGraph, bike: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Union drive and bike graphs, filling missing bike-facility tags."""
    graph = drive.copy()
    graph.add_nodes_from(bike.nodes(data=True))
    for source, target, key, data in bike.edges(keys=True, data=True):
        osmid = _osmid_key(data.get("osmid"))
        matched_key = None
        if graph.has_edge(source, target):
            for existing_key, existing in graph[source][target].items():
                if osmid is not None and _osmid_key(existing.get("osmid")) == osmid:
                    matched_key = existing_key
                    break
        if matched_key is not None:
            existing = graph[source][target][matched_key]
            for tag, value in data.items():
                if existing.get(tag) in (None, "") and value not in (None, ""):
                    existing[tag] = value
        elif osmid is None and graph.has_edge(source, target):
            existing = next(iter(graph[source][target].values()))
            for tag, value in data.items():
                if existing.get(tag) in (None, "") and value not in (None, ""):
                    existing[tag] = value
        else:
            new_key = key
            while graph.has_edge(source, target, new_key):
                new_key = new_key + 1 if isinstance(new_key, int) else 0
            graph.add_edge(source, target, key=new_key, **data)
    return graph


def annotate_park_edges(
    graph: nx.MultiDiGraph,
    bbox: tuple[float, float, float, float],
) -> nx.MultiDiGraph:
    """Mark edges whose midpoint is within ~40 m of a park or forest."""
    try:
        parks = ox.features_from_bbox(
            bbox,
            tags={"leisure": "park", "landuse": "forest"},
        )
    except Exception:
        return graph
    if parks is None or parks.empty:
        return graph

    from shapely.geometry import Point
    from shapely.ops import unary_union

    geoms = [geom for geom in parks.geometry.dropna().tolist() if geom is not None]
    if not geoms:
        return graph
    # ~40 m in degrees at Vancouver latitude
    park_area = unary_union(geoms).buffer(0.00036)
    for source, target, _key, edge_data in graph.edges(keys=True, data=True):
        source_node = graph.nodes[source]
        target_node = graph.nodes[target]
        mid = Point(
            (float(source_node["lon"]) + float(target_node["lon"])) / 2,
            (float(source_node["lat"]) + float(target_node["lat"])) / 2,
        )
        edge_data["in_park"] = bool(park_area.intersects(mid))
    return graph


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
