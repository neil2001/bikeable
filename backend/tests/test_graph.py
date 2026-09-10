from pathlib import Path

import networkx as nx
import pytest
from app.config import settings
from app.graph.fixture import (
    build_tiny_graph,
    load_fixture_graph,
    write_fixture_graphml,
)
from app.graph.loader import load_city_graph
from app.graph.store import (
    load_processed_graph,
    processed_graph_paths,
    read_graph_metadata,
    save_processed_graph,
)
from pytest_mock import MockerFixture


@pytest.fixture
def processed_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "data_root", tmp_path)
    return tmp_path / "processed"


def test_fixture_graph_has_lat_lon_and_length_m() -> None:
    graph = build_tiny_graph()
    assert graph.number_of_nodes() == 4
    assert graph.number_of_edges() == 4

    for _node_id, node_data in graph.nodes(data=True):
        assert "lat" in node_data
        assert "lon" in node_data

    for _source, _target, _key, edge_data in graph.edges(keys=True, data=True):
        assert edge_data["length_m"] > 0


def test_fixture_graph_round_trip(processed_root: Path) -> None:
    graph = build_tiny_graph()
    paths = save_processed_graph(
        graph,
        processed_root=processed_root,
        city_id="fixture",
        source="test-fixture",
    )

    loaded = load_processed_graph(paths)
    metadata = read_graph_metadata(paths)

    assert loaded.number_of_nodes() == graph.number_of_nodes()
    assert loaded.number_of_edges() == graph.number_of_edges()
    assert metadata["cityId"] == "fixture"
    assert metadata["graphVersion"] == "1"
    assert paths.graphml.exists()
    assert paths.pickle.exists()


def test_load_fixture_city_does_not_use_processed_cache(processed_root: Path) -> None:
    graph = load_city_graph("fixture")
    assert isinstance(graph, nx.MultiDiGraph)
    assert graph.number_of_nodes() == 4
    assert not processed_graph_paths(processed_root, "fixture").graphml.exists()


def test_cache_hit_does_not_call_osmnx(
    processed_root: Path,
    mocker: MockerFixture,
) -> None:
    graph = build_tiny_graph()
    save_processed_graph(
        graph,
        processed_root=processed_root,
        city_id="vancouver",
        source="test-cache",
    )

    mock_download = mocker.patch("app.graph.loader.download_city_graph")
    loaded = load_city_graph("vancouver")

    mock_download.assert_not_called()
    assert loaded.number_of_nodes() == graph.number_of_nodes()


def test_cache_miss_downloads_and_persists_graph(
    processed_root: Path,
    mocker: MockerFixture,
) -> None:
    graph = build_tiny_graph()
    mock_download = mocker.patch(
        "app.graph.loader.download_city_graph",
        return_value=graph,
    )

    loaded = load_city_graph("vancouver")
    paths = processed_graph_paths(processed_root, "vancouver")

    mock_download.assert_called_once_with(
        "Vancouver, British Columbia, Canada",
    )
    assert loaded.number_of_nodes() == 4
    assert paths.graphml.exists()
    assert paths.metadata.exists()


def test_fixture_graphml_is_loadable() -> None:
    fixture_path = write_fixture_graphml()
    graph = load_fixture_graph()
    assert fixture_path.exists()
    assert graph.number_of_edges() == 4
