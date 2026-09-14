#!/usr/bin/env python3
from __future__ import annotations

import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.features.apply import apply_features_to_graph
from app.graph.fixture import build_tiny_graph
from app.models.common import Coordinate, RoutePreferences
from app.routing.index import attach_routing_index
from app.routing.point_to_point import route_point_to_point
from app.routing.session import RoutingSession
from app.scoring.score import score_graph
from app.services.city_graph import city_graph_is_available, get_scored_graph


def _time(label: str, fn) -> float:
    start = time.perf_counter()
    fn()
    elapsed = time.perf_counter() - start
    print(f"{label}: {elapsed:.3f}s")
    return elapsed


def bench_fixture() -> None:
    graph = score_graph(apply_features_to_graph(build_tiny_graph()), "road")
    attach_routing_index(graph)
    prefs = RoutePreferences(distance_weight=0.2, bikeability_weight=0.8)
    start = Coordinate(lat=49.2800, lon=-123.1200)
    end = Coordinate(lat=49.2820, lon=-123.1000)

    def run_session() -> None:
        session = RoutingSession.from_graph(graph, prefs)
        session.shortest_path(
            session.nearest_node(start),
            session.nearest_node(end),
        )

    print("Fixture graph")
    _time("session + astar", run_session)
    _time(
        "route_point_to_point",
        lambda: route_point_to_point(graph, start, end, prefs),
    )


def bench_city(city_id: str) -> None:
    if not city_graph_is_available(city_id):
        print(f"Skipping {city_id}: processed graph unavailable")
        return

    _graph, bike_graph = get_scored_graph(city_id, "road")
    prefs = RoutePreferences(distance_weight=0.2, bikeability_weight=0.8)
    start = Coordinate(lat=49.2827, lon=-123.1207)
    end = Coordinate(lat=49.2730, lon=-123.1000)

    print(f"{city_id} graph")
    _time(
        "route_point_to_point",
        lambda: route_point_to_point(bike_graph, start, end, prefs),
    )


def main() -> None:
    bench_fixture()
    processed = BACKEND_ROOT / "data" / "processed"
    if processed.exists():
        for city_dir in sorted(processed.iterdir()):
            if city_dir.is_dir():
                bench_city(city_dir.name)


if __name__ == "__main__":
    main()
