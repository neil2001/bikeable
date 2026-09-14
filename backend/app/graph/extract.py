"""Prepare a single OSM extract for a city bbox (PBF clip or cached XML)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.config import settings
from app.graph.registry import CityDefinition
from app.graph.types import BBox

REGIONAL_PBF_NAME = "british-columbia-latest.osm.pbf"


class OsmExtractError(Exception):
    """Raised when a local OSM extract cannot be prepared."""


def has_usable_extract(city: CityDefinition) -> bool:
    xml_path = city_osm_xml_path(city.city_id)
    if xml_path.exists() and _xml_is_complete(xml_path):
        return True
    pbf_path = city_osm_pbf_path(city.city_id)
    if pbf_path.exists() and _pbf_is_complete(pbf_path):
        return True
    regional = regional_pbf_path()
    return regional.exists() and _pbf_is_complete(regional)


def _xml_is_complete(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 64))
            tail = handle.read().decode("utf-8", errors="ignore")
        return "</osm>" in tail
    except OSError:
        return False


def _pbf_is_complete(path: Path) -> bool:
    osmium = shutil.which("osmium")
    if osmium is None:
        return False
    result = subprocess.run(
        [osmium, "fileinfo", "--extended", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def city_osm_xml_path(city_id: str) -> Path:
    return settings.raw_data_dir / f"{city_id}.osm"


def city_osm_pbf_path(city_id: str) -> Path:
    return settings.raw_data_dir / f"{city_id}.osm.pbf"


def regional_pbf_path() -> Path:
    return settings.raw_data_dir / REGIONAL_PBF_NAME


def resolve_osm_xml(
    city: CityDefinition,
    *,
    osm_path: Path | None = None,
) -> Path:
    """Return an OSM XML file covering the city, clipping a regional PBF if needed."""
    if osm_path is not None:
        return _ensure_xml(osm_path, city)

    xml_path = city_osm_xml_path(city.city_id)
    if xml_path.exists():
        return xml_path

    pbf_path = city_osm_pbf_path(city.city_id)
    if pbf_path.exists():
        return _pbf_to_xml(pbf_path, xml_path)

    regional = regional_pbf_path()
    if regional.exists() and city.osm_bbox is not None:
        clipped = city_osm_pbf_path(city.city_id)
        clip_pbf_to_bbox(regional, city.osm_bbox, clipped)
        return _pbf_to_xml(clipped, xml_path)

    msg = (
        f"No OSM extract for '{city.city_id}'. Place an OSM XML at {xml_path}, "
        f"a city PBF at {pbf_path}, or a regional PBF at {regional}."
    )
    raise OsmExtractError(msg)


def clip_pbf_to_bbox(source_pbf: Path, bbox: BBox, dest_pbf: Path) -> Path:
    osmium = _require_osmium()
    dest_pbf.parent.mkdir(parents=True, exist_ok=True)
    west, south, east, north = bbox
    subprocess.run(
        [
            osmium,
            "extract",
            f"--bbox={west},{south},{east},{north}",
            "--strategy=complete_ways",
            "--overwrite",
            f"--output={dest_pbf}",
            str(source_pbf),
        ],
        check=True,
    )
    return dest_pbf


def _ensure_xml(path: Path, city: CityDefinition) -> Path:
    if path.suffix == ".pbf":
        xml_path = city_osm_xml_path(city.city_id)
        return _pbf_to_xml(path, xml_path)
    if not path.exists():
        msg = f"OSM extract not found at {path}."
        raise OsmExtractError(msg)
    return path


def _pbf_to_xml(source_pbf: Path, dest_xml: Path) -> Path:
    osmium = _require_osmium()
    dest_xml.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            osmium,
            "cat",
            "--overwrite",
            f"--output={dest_xml}",
            str(source_pbf),
        ],
        check=True,
    )
    return dest_xml


def _require_osmium() -> str:
    osmium = shutil.which("osmium")
    if osmium is None:
        msg = (
            "osmium is required to clip or convert PBF extracts "
            "(brew install osmium-tool)."
        )
        raise OsmExtractError(msg)
    return osmium
