from pathlib import Path

import networkx as nx
import pytest
from app.config import settings
from app.graph.fixture import (
    build_tiny_graph,
    load_fixture_graph,
    write_fixture_graphml,
)
from app.graph.loader import GraphPipelineError, load_city_graph
from app.graph.store import (
    GRAPH_VERSION,
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
        assert edge_data.get("osmid") is not None


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
    assert metadata["graphVersion"] == GRAPH_VERSION
    assert paths.graphml.exists()
    assert paths.pickle.exists()


def test_load_fixture_city_does_not_use_processed_cache(processed_root: Path) -> None:
    graph = load_city_graph("fixture")
    assert isinstance(graph, nx.MultiDiGraph)
    assert graph.number_of_nodes() == 4
    assert not processed_graph_paths(processed_root, "fixture").graphml.exists()


def test_cache_hit_does_not_rebuild_osm(
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

    mock_build = mocker.patch("app.graph.loader.build_osm_graph")
    loaded = load_city_graph("vancouver")

    mock_build.assert_not_called()
    assert loaded.number_of_nodes() == graph.number_of_nodes()


def test_cache_miss_builds_from_osm_extract(
    processed_root: Path,
    mocker: MockerFixture,
) -> None:
    graph = build_tiny_graph()
    mock_build = mocker.patch(
        "app.graph.loader.build_osm_graph",
        return_value=graph,
    )

    loaded = load_city_graph("vancouver")
    paths = processed_graph_paths(processed_root, "vancouver")

    mock_build.assert_called_once()
    assert loaded.number_of_nodes() == 4
    assert paths.graphml.exists()
    assert paths.metadata.exists()
    metadata = read_graph_metadata(paths)
    assert metadata["source"].startswith("bbox:")
    assert (paths.city_dir / "qa.json").exists()


def test_graph_from_bbox_uses_one_custom_filter(mocker: MockerFixture) -> None:
    from app.graph.ingest import CUSTOM_FILTER, graph_from_bbox
    from app.graph.registry import VANCOUVER

    graph = build_tiny_graph()
    mock_from_bbox = mocker.patch(
        "app.graph.ingest.ox.graph_from_bbox",
        return_value=graph,
    )
    mocker.patch("app.graph.ingest.ox.project_graph", return_value=graph)
    mocker.patch(
        "app.graph.ingest.ox.features_from_bbox",
        side_effect=Exception("offline"),
    )

    result = graph_from_bbox(VANCOUVER)
    mock_from_bbox.assert_called_once()
    kwargs = mock_from_bbox.call_args.kwargs
    assert kwargs["custom_filter"] == CUSTOM_FILTER
    assert kwargs["simplify"] is True
    assert result.number_of_nodes() == graph.number_of_nodes()


def test_build_errors_when_extract_missing(
    processed_root: Path,
    mocker: MockerFixture,
) -> None:
    from app.graph.extract import OsmExtractError

    mocker.patch(
        "app.graph.loader.build_osm_graph",
        side_effect=OsmExtractError("No OSM extract"),
    )
    with pytest.raises(GraphPipelineError, match="No OSM extract"):
        load_city_graph("vancouver")


def test_fixture_graphml_is_loadable() -> None:
    fixture_path = write_fixture_graphml()
    graph = load_fixture_graph()
    assert fixture_path.exists()
    assert graph.number_of_edges() >= 4


def test_configure_osmnx_retains_cycling_tags() -> None:
    import osmnx as ox
    from app.graph.ingest import EXTRA_WAY_TAGS, configure_osmnx_tags

    configure_osmnx_tags()
    for tag in EXTRA_WAY_TAGS:
        assert tag in ox.settings.useful_tags_way


def test_keep_ingest_edge_drops_motorway_and_private() -> None:
    from app.graph.ingest import keep_ingest_edge

    assert keep_ingest_edge({"highway": "residential"})
    assert keep_ingest_edge({"highway": "cycleway"})
    assert keep_ingest_edge({"highway": "footway"})
    assert not keep_ingest_edge({"highway": "motorway"})
    assert not keep_ingest_edge({"highway": "residential", "bicycle": "no"})
    assert not keep_ingest_edge({"highway": "residential", "access": "private"})


def test_drop_excluded_edges_removes_motorways() -> None:
    from app.graph.ingest import _drop_excluded_edges

    graph = nx.MultiDiGraph()
    graph.add_node(1, lat=49.28, lon=-123.12, x=-123.12, y=49.28)
    graph.add_node(2, lat=49.281, lon=-123.11, x=-123.11, y=49.281)
    graph.add_node(3, lat=49.282, lon=-123.10, x=-123.10, y=49.282)
    graph.add_edge(1, 2, key=0, highway="residential", length=100.0)
    graph.add_edge(2, 3, key=0, highway="cycleway", length=100.0)
    graph.add_edge(1, 3, key=0, highway="motorway", length=200.0)
    filtered = _drop_excluded_edges(graph)
    highways = {
        data.get("highway")
        for _u, _v, _k, data in filtered.edges(keys=True, data=True)
    }
    assert highways == {"residential", "cycleway"}
    assert nx.is_weakly_connected(filtered)
