"""Build and read Mapbox vector tiles for the bikeability road overlay."""

from __future__ import annotations

import gzip
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mapbox_vector_tile
import mercantile
from app.services.bikeability_map import OverlayGeoJSON
from pmtiles.reader import MmapSource, Reader
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer
from shapely.geometry import LineString, box, mapping, shape
from shapely.strtree import STRtree

SOURCE_LAYER = "roads"
MIN_ZOOM = 8
MAX_ZOOM = 14
TILE_EXTENT = 4096
TILE_BUFFER_RATIO = 64 / TILE_EXTENT


@dataclass(frozen=True)
class IndexedRoad:
    road_id: str
    bikeability: float
    geometry: LineString


def overlay_bbox(overlay: OverlayGeoJSON) -> tuple[float, float, float, float]:
    """Return (west, south, east, north) in WGS84."""
    west = math.inf
    south = math.inf
    east = -math.inf
    north = -math.inf
    for feature in overlay.get("features", []):
        geom = shape(feature["geometry"])
        bounds = geom.bounds
        west = min(west, bounds[0])
        south = min(south, bounds[1])
        east = max(east, bounds[2])
        north = max(north, bounds[3])
    if west == math.inf:
        return (-180.0, -85.0, 180.0, 85.0)
    return (west, south, east, north)


def _index_roads(overlay: OverlayGeoJSON) -> tuple[list[IndexedRoad], STRtree]:
    roads: list[IndexedRoad] = []
    geoms: list[LineString] = []
    for feature in overlay.get("features", []):
        geom = shape(feature["geometry"])
        if geom.geom_type != "LineString" or len(geom.coords) < 2:
            continue
        props = feature.get("properties", {})
        roads.append(
            IndexedRoad(
                road_id=str(props["roadId"]),
                bikeability=float(props["bikeability"]),
                geometry=geom,
            )
        )
        geoms.append(geom)
    tree = STRtree(geoms)
    return roads, tree


def _tile_polygon(z: int, x: int, y: int) -> Any:
    bounds = mercantile.bounds(x, y, z)
    width = bounds.east - bounds.west
    height = bounds.north - bounds.south
    pad_x = width * TILE_BUFFER_RATIO
    pad_y = height * TILE_BUFFER_RATIO
    return box(
        bounds.west - pad_x,
        bounds.south - pad_y,
        bounds.east + pad_x,
        bounds.north + pad_y,
    )


def _linestrings_from_intersection(intersection: Any) -> list[LineString]:
    if intersection.is_empty:
        return []
    geom_type = intersection.geom_type
    if geom_type == "LineString":
        return [intersection] if len(intersection.coords) >= 2 else []
    if geom_type == "MultiLineString":
        return [g for g in intersection.geoms if len(g.coords) >= 2]
    if geom_type == "GeometryCollection":
        lines: list[LineString] = []
        for geom in intersection.geoms:
            lines.extend(_linestrings_from_intersection(geom))
        return lines
    return []


def _encode_tile(
    z: int,
    x: int,
    y: int,
    roads: list[IndexedRoad],
    tree: STRtree,
) -> bytes | None:
    tile_poly = _tile_polygon(z, x, y)
    bounds = mercantile.bounds(x, y, z)
    quantize = (bounds.west, bounds.south, bounds.east, bounds.north)

    mvt_features: list[dict[str, Any]] = []
    for index in tree.query(tile_poly, predicate="intersects"):
        road = roads[int(index)]
        clipped = road.geometry.intersection(tile_poly)
        for line in _linestrings_from_intersection(clipped):
            mvt_features.append(
                {
                    "geometry": mapping(line),
                    "properties": {
                        "roadId": road.road_id,
                        "bikeability": road.bikeability,
                    },
                }
            )

    if not mvt_features:
        return None

    layers = [{"name": SOURCE_LAYER, "features": mvt_features}]
    mvt = mapbox_vector_tile.encode(
        layers,
        default_options={
            "quantize_bounds": quantize,
            "extents": TILE_EXTENT,
        },
    )
    return gzip.compress(mvt, mtime=0)


def write_overlay_pmtiles(
    overlay: OverlayGeoJSON,
    dest_path: Path,
    *,
    bbox: tuple[float, float, float, float] | None = None,
) -> None:
    """Write a PMTiles archive with gzip-compressed MVT tiles."""
    west, south, east, north = bbox or overlay_bbox(overlay)
    roads, tree = _index_roads(overlay)

    tile_coords: list[tuple[int, int, int]] = []
    for zoom in range(MIN_ZOOM, MAX_ZOOM + 1):
        for tile in mercantile.tiles(west, south, east, north, zooms=zoom):
            tile_coords.append((tile.z, tile.x, tile.y))
    tile_coords.sort(key=lambda item: zxy_to_tileid(item[0], item[1], item[2]))

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_name(f"{dest_path.name}.tmp")
    center_lon = (west + east) / 2
    center_lat = (south + north) / 2
    header = {
        "version": 3,
        "root_offset": 0,
        "root_length": 0,
        "metadata_offset": 0,
        "metadata_length": 0,
        "leaf_directory_offset": 0,
        "leaf_directory_length": 0,
        "tile_data_offset": 0,
        "tile_data_length": 0,
        "addressed_tiles_count": 0,
        "tile_entries_count": 0,
        "tile_contents_count": 0,
        "clustered": True,
        "internal_compression": Compression.GZIP,
        "tile_compression": Compression.GZIP,
        "tile_type": TileType.MVT,
        "min_zoom": MIN_ZOOM,
        "max_zoom": MAX_ZOOM,
        "min_lon_e7": int(west * 1e7),
        "min_lat_e7": int(south * 1e7),
        "max_lon_e7": int(east * 1e7),
        "max_lat_e7": int(north * 1e7),
        "center_zoom": max(MIN_ZOOM, min(MAX_ZOOM, 12)),
        "center_lon_e7": int(center_lon * 1e7),
        "center_lat_e7": int(center_lat * 1e7),
    }
    metadata = {
        "name": overlay.get("cityId", "overlay"),
        "description": "Bikeability road overlay",
        "format": "pbf",
        "type": "overlay",
        "version": str(overlay.get("scoreVersion", "")),
    }

    with tmp_path.open("wb") as handle:
        writer = Writer(handle)
        for z, x, y in tile_coords:
            tile_bytes = _encode_tile(z, x, y, roads, tree)
            if tile_bytes is None:
                continue
            writer.write_tile(zxy_to_tileid(z, x, y), tile_bytes)
        writer.finalize(header, metadata)
    tmp_path.replace(dest_path)


def open_pmtiles_reader(path: Path) -> tuple[Reader, Any]:
    """Open a PMTiles reader; caller must keep the file handle alive."""
    handle = path.open("rb")
    return Reader(MmapSource(handle)), handle


def read_tile_mvt(path: Path, z: int, x: int, y: int) -> bytes | None:
    """Return decompressed MVT bytes for a tile, or None if missing."""
    reader, handle = open_pmtiles_reader(path)
    try:
        raw = reader.get(z, x, y)
        if raw is None:
            return None
        header = reader.header()
        if header["tile_compression"] == Compression.GZIP:
            return gzip.decompress(raw)
        return bytes(raw)
    finally:
        handle.close()
