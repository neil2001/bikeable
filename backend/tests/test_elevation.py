import json
from unittest.mock import MagicMock

import pytest
from app.config import settings
from app.elevation.open_meteo import clear_elevation_cache, lookup_elevations
from app.elevation.provider import sample_path_elevations
from app.features.apply import apply_features_to_graph
from app.graph.fixture import build_tiny_graph
from app.main import app
from app.routing.metrics import compute_route_metrics
from app.scoring.score import score_graph
from fastapi.testclient import TestClient

client = TestClient(app)


def test_lookup_elevations_parses_open_meteo_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_elevation_cache()
    payload = json.dumps({"elevation": [12.5, 18.0]}).encode()
    response = MagicMock()
    response.read.return_value = payload
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: response)

    elevations = lookup_elevations(
        [(49.28, -123.12), (49.281, -123.11)],
        api_url="https://api.open-meteo.com/v1/elevation",
    )
    assert elevations == [12.5, 18.0]


def test_lookup_elevations_returns_nones_when_request_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_elevation_cache()

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise TimeoutError("offline")

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    elevations = lookup_elevations(
        [(49.28, -123.12)],
        api_url="https://api.open-meteo.com/v1/elevation",
    )
    assert elevations == [None]


def test_sample_path_elevations_uses_open_meteo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = score_graph(apply_features_to_graph(build_tiny_graph()), "road")
    monkeypatch.setattr(settings, "elevation_provider", "open_meteo")
    monkeypatch.setattr(
        "app.elevation.provider.lookup_elevations",
        lambda coords, api_url: [10.0 + index for index, _coord in enumerate(coords)],
    )
    elevations = sample_path_elevations(graph, [1, 2, 3])
    assert elevations == [10.0, 11.0, 12.0]
    metrics = compute_route_metrics(graph, [1, 2, 3], elevations=elevations)
    assert metrics.elevation_gain_m == pytest.approx(2.0)
    assert [sample.elevation_m for sample in metrics.profile] == [10.0, 11.0, 12.0]


def test_manual_route_includes_elevation_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "elevation_provider", "open_meteo")
    monkeypatch.setattr(
        "app.services.routing.sample_path_elevations",
        lambda _graph, path: [20.0 + index * 3.0 for index, _node in enumerate(path)],
    )
    response = client.post(
        "/api/v1/routes/manual?cityId=fixture",
        json={
            "waypoints": [
                {"lat": 49.2800, "lon": -123.1200},
                {"lat": 49.2820, "lon": -123.1000},
            ],
            "profile": "road",
            "preferences": {"distanceWeight": 0.2, "bikeabilityWeight": 0.8},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]
    assert all(sample["elevationM"] is not None for sample in payload["profile"])
    assert payload["elevationGainM"] > 0
