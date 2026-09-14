from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import networkx as nx
import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree

from app.models.common import Coordinate
from app.scoring.config import RoutingCostParams, cached_scoring_config

ROUTING_INDEX_KEY = "_routing_index"


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

    @classmethod
    def from_graph(cls, graph: nx.MultiDiGraph) -> RoutingIndex:
        routing = cached_scoring_config().routing
        crs = graph.graph.get("crs")
        crs_key = str(crs) if crs else None
        node_ids: list[int] = []
        node_x: list[float] = []
        node_y: list[float] = []
        node_lat: list[float] = []
        node_lon: list[float] = []

        for node_id, node_data in graph.nodes(data=True):
            lat = float(node_data["lat"])
            lon = float(node_data["lon"])
            x, y = _latlon_to_xy(crs_key, lat, lon)
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

        edge_records: list[EdgeRecord] = []
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

        return cls(
            node_ids=ids_array,
            node_x=x_array,
            node_y=y_array,
            node_lat=lat_array,
            node_lon=lon_array,
            edges=tuple(edge_records),
            crs=crs_key,
            _tree=tree,
        )

    def nearest_node(self, point: Coordinate) -> int:
        x, y = _latlon_to_xy(self.crs, point.lat, point.lon)
        _distance, index = self._tree.query([x, y])
        return int(self.node_ids[int(index)])

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
        index = int(np.where(self.node_ids == node_id)[0][0])
        return float(self.node_x[index]), float(self.node_y[index])

    def node_coordinate(self, node_id: int) -> Coordinate:
        index = int(np.where(self.node_ids == node_id)[0][0])
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
