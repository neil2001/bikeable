from __future__ import annotations

from collections import OrderedDict
from functools import lru_cache
from typing import Any

import networkx as nx
import numpy as np

from app.models.common import Coordinate, RoutePreferences
from app.routing.cost import edge_routing_costs_vectorized
from app.routing.errors import RoutingError
from app.routing.index import RoutingIndex, get_routing_index
from app.scoring.config import cached_scoring_config

_COST_CACHE_LIMIT = 24
_cost_table_cache: OrderedDict[tuple[Any, ...], np.ndarray] = OrderedDict()


class RoutingSession:
    def __init__(
        self,
        graph: nx.MultiDiGraph,
        index: RoutingIndex,
        preferences: RoutePreferences,
        *,
        cache_key: tuple[Any, ...] | None = None,
    ) -> None:
        self.graph = graph
        self.index = index
        self.preferences = preferences
        self._cache_key = cache_key
        self._edge_costs = self._load_edge_costs()
        self._min_cost_per_meter = self._compute_min_cost_per_meter()
        self._parallel_cost_lookup = self._build_parallel_cost_lookup()

    @classmethod
    def from_graph(
        cls,
        graph: nx.MultiDiGraph,
        preferences: RoutePreferences,
        *,
        cache_key: tuple[Any, ...] | None = None,
    ) -> RoutingSession:
        return cls(
            graph,
            get_routing_index(graph),
            preferences,
            cache_key=cache_key,
        )

    def nearest_node(self, point: Coordinate) -> int:
        return self.index.nearest_node(point)

    def shortest_path(self, start_node: int, end_node: int) -> list[int]:
        try:
            return nx.astar_path(
                self.graph,
                start_node,
                end_node,
                heuristic=self._heuristic,
                weight=self._weight,
            )
        except nx.NetworkXNoPath as exc:
            raise RoutingError(
                "ROUTE_NOT_FOUND",
                "No valid cycling route could be constructed.",
            ) from exc

    def edge_cost(self, source: int, target: int, key: int) -> float:
        return self._parallel_cost_lookup.get((source, target, key), float("inf"))

    def select_edge_data(self, source: int, target: int) -> dict[str, Any]:
        edges = self.graph.get_edge_data(source, target)
        if not edges:
            msg = f"No edge from {source} to {target}."
            raise ValueError(msg)
        best_key = min(
            edges,
            key=lambda edge_key: self.edge_cost(source, target, int(edge_key)),
        )
        return edges[best_key]

    def _load_edge_costs(self) -> np.ndarray:
        if self._cache_key is not None:
            cached = _cost_table_cache.get(self._cache_key)
            if cached is not None:
                _cost_table_cache.move_to_end(self._cache_key)
                return cached

        routing = cached_scoring_config().routing
        length_m = np.fromiter(
            (edge.length_m for edge in self.index.edges),
            dtype=np.float64,
            count=len(self.index.edges),
        )
        penalty = np.fromiter(
            (edge.penalty for edge in self.index.edges),
            dtype=np.float64,
            count=len(self.index.edges),
        )
        costs = edge_routing_costs_vectorized(
            length_m,
            penalty,
            self.preferences,
            routing=routing,
        )
        if self._cache_key is not None:
            _cost_table_cache[self._cache_key] = costs
            _cost_table_cache.move_to_end(self._cache_key)
            while len(_cost_table_cache) > _COST_CACHE_LIMIT:
                _cost_table_cache.popitem(last=False)
        return costs

    def _build_parallel_cost_lookup(self) -> dict[tuple[int, int, int], float]:
        lookup: dict[tuple[int, int, int], float] = {}
        for edge, cost in zip(self.index.edges, self._edge_costs, strict=True):
            key = (edge.source, edge.target, edge.key)
            current = lookup.get(key)
            if current is None or cost < current:
                lookup[key] = float(cost)
        return lookup

    def _compute_min_cost_per_meter(self) -> float:
        if not self.index.edges:
            return self.preferences.distance_weight
        ratios = [
            cost / edge.length_m
            for edge, cost in zip(self.index.edges, self._edge_costs, strict=True)
            if edge.length_m > 0
        ]
        if not ratios:
            return self.preferences.distance_weight
        return min(min(ratios), self.preferences.distance_weight)

    def _weight(
        self,
        source: int,
        target: int,
        keyed_edges: dict[int, dict[str, Any]],
    ) -> float:
        return min(
            self.edge_cost(source, target, int(key))
            for key in keyed_edges
        )

    def _heuristic(self, node_id: int, goal_id: int) -> float:
        if node_id == goal_id:
            return 0.0
        x1, y1 = self.index.node_xy(node_id)
        x2, y2 = self.index.node_xy(goal_id)
        return self._min_cost_per_meter * float(np.hypot(x2 - x1, y2 - y1))


@lru_cache(maxsize=128)
def quantize_distance_weight(distance_weight: float) -> float:
    return round(distance_weight, 1)


def preference_cache_key(
    city_id: str,
    graph_version: str,
    score_version: str,
    preferences: RoutePreferences,
) -> tuple[str, str, str, float]:
    return (
        city_id,
        graph_version,
        score_version,
        quantize_distance_weight(preferences.distance_weight),
    )


def clear_cost_table_cache() -> None:
    _cost_table_cache.clear()
    quantize_distance_weight.cache_clear()
