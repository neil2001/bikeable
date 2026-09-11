from dataclasses import dataclass

BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class SectionDefinition:
    section_id: str
    name: str
    osm_bbox: BBox


@dataclass(frozen=True)
class CityDefinition:
    city_id: str
    name: str
    osm_place: str | None = None
    osm_bbox: BBox | None = None
    sections: tuple[SectionDefinition, ...] = ()
    is_fixture: bool = False


# west, south, east, north — UBC through Vancouver, West Van, and North Van.
VANCOUVER_BBOX: BBox = (-123.285, 49.198, -122.95, 49.375)

# Overlapping section bboxes (~250–400 m) whose union equals VANCOUVER_BBOX.
VANCOUVER_SECTIONS: tuple[SectionDefinition, ...] = (
    SectionDefinition(
        section_id="ubc",
        name="UBC / Point Grey",
        osm_bbox=(-123.285, 49.198, -123.155, 49.282),
    ),
    SectionDefinition(
        section_id="vancouver_core",
        name="Vancouver core",
        osm_bbox=(-123.265, 49.218, -123.085, 49.318),
    ),
    SectionDefinition(
        section_id="west_van",
        name="West Vancouver",
        osm_bbox=(-123.285, 49.278, -123.155, 49.375),
    ),
    SectionDefinition(
        section_id="north_van",
        name="North Vancouver",
        osm_bbox=(-123.245, 49.278, -122.95, 49.375),
    ),
)

VANCOUVER = CityDefinition(
    city_id="vancouver",
    name="Vancouver metro",
    osm_bbox=VANCOUVER_BBOX,
    sections=VANCOUVER_SECTIONS,
)

FIXTURE = CityDefinition(
    city_id="fixture",
    name="Fixture Graph",
    is_fixture=True,
)

CITY_REGISTRY: dict[str, CityDefinition] = {
    VANCOUVER.city_id: VANCOUVER,
    FIXTURE.city_id: FIXTURE,
}


def get_city_definition(city_id: str) -> CityDefinition:
    city = CITY_REGISTRY.get(city_id)
    if city is None:
        msg = f"Unknown city '{city_id}'."
        raise KeyError(msg)
    return city


def city_source_label(city: CityDefinition) -> str:
    if city.sections:
        section_ids = ",".join(section.section_id for section in city.sections)
        return f"sections:{section_ids}"
    if city.osm_bbox is not None:
        west, south, east, north = city.osm_bbox
        return f"bbox:{west},{south},{east},{north}"
    if city.osm_place is not None:
        return city.osm_place
    return city.city_id
