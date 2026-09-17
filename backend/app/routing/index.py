from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import TypeAlias

import networkx as nx
import numpy as np
from app.models.common import Coordinate
from app.scoring.config import RoutingCostParams, cached_scoring_config
from pyproj import Transformer
from scipy.spatial import cKDTree

ROUTING_INDEX_KEY = "_routing_index"
EDGE_SAMPLE_SPACING_M = 100.0
CANDIDATE_EDGE_RADIUS_M = 300.0

EdgeKey: TypeAlias = tuple[int, int, int]


@lru_cache(maxsize=32)
def _wgs84_to_crs_transformer(crs: str) -> Transformer:
    return Transformer.from_crs("EPSG:4326", crs, always_xy=True)


def _latlon_to_xy(crs: str | None, lat: float, lon: float) -> tuple[float, float]:
    if crs:
        x, y = _wgs84_to_crs_transformer(crs).transform(lon, lat)
        return float(x), float(y)
    x = lon * 111_320 * np.cos(np.radians(lat))
    y = lat * 111_320
    return x, y


@dataclass(frozen=True)
class EdgeRecord:
    source: int
    target: int
    key: int
    length_m: float
    bikeability: float
    penalty: float


def _projected_xy_are_metric(graph: nx.MultiDiGraph) -> bool:
    crs = graph.graph.get("crs")
    if not crs or "4326" in str(crs) or graph.number_of_nodes() == 0:
        return False
    _node_id, node_data = next(iter(graph.nodes(data=True)))
    if "x" not in node_data or "y" not in node_data:
        return False
    if "lat" not in node_data or "lon" not in node_data:
        return True
    try:
        x, y = _wgs84_to_crs_transformer(str(crs)).transform(
            float(node_data["lon"]),
            float(node_data["lat"]),
        )
    except Exception:
        return False
    error = math.hypot(x - float(node_data["x"]), y - float(node_data["y"]))
    return error < 50.0


def _node_xy_for_index(
    node_data: dict,
    *,
    uses_metric_xy: bool,
    crs_key: str | None,
) -> tuple[float, float]:
    lat = float(node_data["lat"])
    lon = float(node_data["lon"])
    if uses_metric_xy and "x" in node_data and "y" in node_data:
        return float(node_data["x"]), float(node_data["y"])
    if uses_metric_xy and crs_key:
        return _latlon_to_xy(crs_key, lat, lon)
    return lon, lat


def _edge_coords_for_index(
    source: int,
    target: int,
    edge_data: dict,
    xy_by_node: dict[int, tuple[float, float]],
    graph: nx.MultiDiGraph,
    *,
    uses_metric_xy: bool,
) -> list[tuple[float, float]]:
    geom = edge_data.get("geometry")
    if geom is not None and hasattr(geom, "coords"):
        if uses_metric_xy:
            return [(float(x), float(y)) for x, y in geom.coords]
        return [(float(x), float(y)) for x, y in geom.coords]
    source_node = graph.nodes[source]
    target_node = graph.nodes[target]
    if uses_metric_xy:
        return [xy_by_node[source], xy_by_node[target]]
    return [
        (float(source_node["lon"]), float(source_node["lat"])),
        (float(target_node["lon"]), float(target_node["lat"])),
    ]


def _spacing_in_coord_units(
    spacing_m: float,
    *,
    uses_metric_xy: bool,
    ref_lat: float,
) -> float:
    if uses_metric_xy:
        return spacing_m
    return spacing_m / (111_320 * max(math.cos(math.radians(ref_lat)), 1e-6))


def _densify_coords(
    coords: list[tuple[float, float]],
    spacing: float,
) -> list[tuple[float, float]]:
    if len(coords) < 2:
        return coords
    dense: list[tuple[float, float]] = [coords[0]]
    for start, end in zip(coords, coords[1:], strict=False):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        segment_len = float(np.hypot(dx, dy))
        if segment_len <= spacing:
            if dense[-1] != end:
                dense.append(end)
            continue
        steps = max(1, int(np.ceil(segment_len / spacing)))
        for step in range(1, steps + 1):
            t = step / steps
            point = (start[0] + t * dx, start[1] + t * dy)
            if dense[-1] != point:
                dense.append(point)
    return dense


@dataclass
class RoutingIndex:
    node_ids: np.ndarray
    node_x: np.ndarray
    node_y: np.ndarray
    node_lat: np.ndarray
    node_lon: np.ndarray
    edges: tuple[EdgeRecord, ...]
    crs: str | None
    _tree: cKDTree
    _node_index: dict[int, int]
    _edge_sample_tree: cKDTree
    _edge_sample_keys: tuple[EdgeKey, ...]
    _uses_metric_xy: bool

    @classmethod
    def from_graph(cls, graph: nx.MultiDiGraph) -> RoutingIndex:
        routing = cached_scoring_config().routing
        crs = graph.graph.get("crs")
        crs_key = str(crs) if crs else None
        uses_metric_xy = _projected_xy_are_metric(graph)
        node_ids: list[int] = []
        node_x: list[float] = []
        node_y: list[float] = []
        node_lat: list[float] = []
        node_lon: list[float] = []

        for node_id, node_data in graph.nodes(data=True):
            lat = float(node_data["lat"])
            lon = float(node_data["lon"])
            x, y = _node_xy_for_index(
                node_data,
                uses_metric_xy=uses_metric_xy,
                crs_key=crs_key,
            )
            node_ids.append(int(node_id))
            node_x.append(x)
            node_y.append(y)
            node_lat.append(lat)
            node_lon.append(lon)

        if not node_ids:
            msg = "Graph has no nodes to index."
            raise ValueError(msg)

        ids_array = np.asarray(node_ids, dtype=np.int64)
        x_array = np.asarray(node_x, dtype=np.float64)
        y_array = np.asarray(node_y, dtype=np.float64)
        lat_array = np.asarray(node_lat, dtype=np.float64)
        lon_array = np.asarray(node_lon, dtype=np.float64)
        tree = cKDTree(np.column_stack((x_array, y_array)))
        node_index = {int(node_id): index for index, node_id in enumerate(node_ids)}

        xy_by_node = {
            int(node_id): (float(x), float(y))
            for node_id, x, y in zip(node_ids, node_x, node_y, strict=True)
        }

        edge_records: list[EdgeRecord] = []
        sample_points: list[tuple[float, float]] = []
        sample_keys: list[EdgeKey] = []
        for source, target, key, edge_data in graph.edges(keys=True, data=True):
            length_m = float(edge_data.get("length_m", edge_data.get("length", 1.0)))
            bikeability = float(edge_data.get("bikeability", 5.0))
            penalty = _edge_penalty(bikeability, routing)
            edge_records.append(
                EdgeRecord(
                    source=int(source),
                    target=int(target),
                    key=int(key),
                    length_m=length_m,
                    bikeability=bikeability,
                    penalty=penalty,
                ),
            )
            coords = _edge_coords_for_index(
                int(source),
                int(target),
                edge_data,
                xy_by_node,
                graph,
                uses_metric_xy=uses_metric_xy,
            )
            source_lat = float(graph.nodes[source]["lat"])
            target_lat = float(graph.nodes[target]["lat"])
            ref_lat = (source_lat + target_lat) / 2
            spacing = _spacing_in_coord_units(
                EDGE_SAMPLE_SPACING_M,
                uses_metric_xy=uses_metric_xy,
                ref_lat=ref_lat,
            )
            for x, y in _densify_coords(coords, spacing):
                sample_points.append((x, y))
                sample_keys.append((int(source), int(target), int(key)))

        if sample_points:
            edge_sample_tree = cKDTree(np.asarray(sample_points, dtype=np.float64))
        else:
            edge_sample_tree = cKDTree(np.empty((0, 2)))

        return cls(
            node_ids=ids_array,
            node_x=x_array,
            node_y=y_array,
            node_lat=lat_array,
            node_lon=lon_array,
            edges=tuple(edge_records),
            crs=crs_key,
            _tree=tree,
            _node_index=node_index,
            _edge_sample_tree=edge_sample_tree,
            _edge_sample_keys=tuple(sample_keys),
            _uses_metric_xy=uses_metric_xy,
        )

    def nearest_node(self, point: Coordinate) -> int:
        x, y = _latlon_to_xy(self.crs, point.lat, point.lon)
        _distance, index = self._tree.query([x, y])
        return int(self.node_ids[int(index)])

    def candidate_edges(
        self,
        point: Coordinate,
        *,
        radius_m: float = CANDIDATE_EDGE_RADIUS_M,
    ) -> list[EdgeKey]:
        if len(self._edge_sample_keys) == 0:
            return []
        if self._uses_metric_xy and self.crs:
            x, y = _latlon_to_xy(self.crs, point.lat, point.lon)
            radius = radius_m
        else:
            x, y = point.lon, point.lat
            radius = radius_m / (
                111_320 * max(math.cos(math.radians(point.lat)), 1e-6)
            )
        indices = self._edge_sample_tree.query_ball_point([x, y], r=radius)
        if not indices:
            return []
        seen: set[EdgeKey] = set()
        candidates: list[EdgeKey] = []
        for raw_index in indices:
            key = self._edge_sample_keys[int(raw_index)]
            if key in seen:
                continue
            seen.add(key)
            candidates.append(key)
        return candidates

    def nodes_in_annulus(
        self,
        center_x: float,
        center_y: float,
        inner_radius_m: float,
        outer_radius_m: float,
    ) -> list[int]:
        outer_indices = self._tree.query_ball_point(
            [center_x, center_y],
            r=outer_radius_m,
        )
        if inner_radius_m <= 0:
            return [int(self.node_ids[index]) for index in outer_indices]

        inner_indices = set(
            self._tree.query_ball_point([center_x, center_y], r=inner_radius_m),
        )
        return [
            int(self.node_ids[index])
            for index in outer_indices
            if index not in inner_indices
        ]

    def node_xy(self, node_id: int) -> tuple[float, float]:
        index = self._node_index[int(node_id)]
        return float(self.node_x[index]), float(self.node_y[index])

    def node_coordinate(self, node_id: int) -> Coordinate:
        index = self._node_index[int(node_id)]
        return Coordinate(
            lat=float(self.node_lat[index]),
            lon=float(self.node_lon[index]),
        )


def _edge_penalty(bikeability: float, routing: RoutingCostParams) -> float:
    discomfort = 1.0 - bikeability / 10.0
    penalty = discomfort**routing.gamma
    if bikeability < routing.avoid_score:
        penalty *= routing.avoid_factor
    return penalty


def get_routing_index(graph: nx.MultiDiGraph) -> RoutingIndex:
    existing = graph.graph.get(ROUTING_INDEX_KEY)
    if isinstance(existing, RoutingIndex):
        return existing
    index = RoutingIndex.from_graph(graph)
    graph.graph[ROUTING_INDEX_KEY] = index
    return index


def attach_routing_index(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    graph.graph[ROUTING_INDEX_KEY] = RoutingIndex.from_graph(graph)
    return graph
