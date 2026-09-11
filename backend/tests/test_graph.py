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
    assert graph.number_of_edges() >= 4

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
    mock_build = mocker.patch(
        "app.graph.loader._build_sectioned_graph",
        return_value=graph,
    )

    loaded = load_city_graph("vancouver")
    paths = processed_graph_paths(processed_root, "vancouver")

    mock_build.assert_called_once()
    called_city_id, called_sections = mock_build.call_args.args[:2]
    assert called_city_id == "vancouver"
    assert len(called_sections) == 4
    assert loaded.number_of_nodes() == 4
    assert paths.graphml.exists()
    assert paths.metadata.exists()


def test_fixture_graphml_is_loadable() -> None:
    fixture_path = write_fixture_graphml()
    graph = load_fixture_graph()
    assert fixture_path.exists()
    assert graph.number_of_edges() >= 4


def test_download_city_graph_uses_bbox(mocker: MockerFixture) -> None:
    from app.graph.ingest import download_city_graph
    from app.graph.registry import VANCOUVER

    graph = build_tiny_graph()
    mock_from_bbox = mocker.patch(
        "app.graph.ingest.ox.graph_from_bbox",
        return_value=graph,
    )
    mocker.patch("app.graph.ingest.ox.project_graph", return_value=graph)
    mocker.patch("app.graph.ingest.ox.graph_from_place")
    mocker.patch(
        "app.graph.ingest.ox.features_from_bbox",
        side_effect=Exception("offline"),
    )

    result = download_city_graph(VANCOUVER)

    assert mock_from_bbox.call_count == 2
    mock_from_bbox.assert_any_call(
        VANCOUVER.osm_bbox,
        network_type="drive",
        simplify=True,
        truncate_by_edge=True,
    )
    mock_from_bbox.assert_any_call(
        VANCOUVER.osm_bbox,
        network_type="bike",
        simplify=True,
        truncate_by_edge=True,
    )
    assert result.number_of_nodes() == graph.number_of_nodes()


def test_configure_osmnx_retains_cycling_tags() -> None:
    import osmnx as ox
    from app.graph.ingest import EXTRA_WAY_TAGS, configure_osmnx_tags

    configure_osmnx_tags()
    for tag in EXTRA_WAY_TAGS:
        assert tag in ox.settings.useful_tags_way


def test_merge_graphs_keeps_cycleway_tags() -> None:
    from app.graph.ingest import merge_graphs

    drive = nx.MultiDiGraph()
    drive.add_node(1, lat=49.28, lon=-123.12, x=0.0, y=0.0)
    drive.add_node(2, lat=49.29, lon=-123.11, x=100.0, y=0.0)
    drive.add_edge(
        1,
        2,
        key=0,
        osmid=100,
        highway="tertiary",
        length=50.0,
        length_m=50.0,
    )

    bike = nx.MultiDiGraph()
    bike.add_node(1, lat=49.28, lon=-123.12, x=0.0, y=0.0)
    bike.add_node(2, lat=49.29, lon=-123.11, x=100.0, y=0.0)
    bike.add_edge(
        1,
        2,
        key=0,
        osmid=100,
        highway="tertiary",
        length=50.0,
        length_m=50.0,
        **{"cycleway:right": "separate", "surface": "asphalt", "bicycle": "yes"},
    )

    merged = merge_graphs(drive, bike)
    data = merged[1][2][0]
    assert data["cycleway:right"] == "separate"
    assert data["surface"] == "asphalt"
    assert data["bicycle"] == "yes"


def test_merge_graphs_includes_exclusive_cycleway() -> None:
    from app.graph.ingest import merge_graphs

    drive = nx.MultiDiGraph()
    drive.add_node(1, lat=49.28, lon=-123.12, x=0.0, y=0.0)
    drive.add_node(2, lat=49.29, lon=-123.11, x=100.0, y=0.0)
    drive.add_edge(1, 2, key=0, osmid=100, highway="tertiary", length=50.0)

    bike = nx.MultiDiGraph()
    bike.add_node(1, lat=49.28, lon=-123.12, x=0.0, y=0.0)
    bike.add_node(2, lat=49.29, lon=-123.11, x=100.0, y=0.0)
    bike.add_node(3, lat=49.30, lon=-123.10, x=200.0, y=0.0)
    bike.add_edge(1, 2, key=0, osmid=100, highway="tertiary", length=50.0)
    bike.add_edge(
        2,
        3,
        key=0,
        osmid=200,
        highway="cycleway",
        length=80.0,
        bicycle="designated",
    )

    merged = merge_graphs(drive, bike)
    cycleways = [
        data
        for *_rest, data in merged.edges(keys=True, data=True)
        if data.get("highway") == "cycleway"
    ]
    assert len(cycleways) == 1
    assert cycleways[0]["bicycle"] == "designated"
