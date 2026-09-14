from dataclasses import dataclass

from app.graph.types import BBox


@dataclass(frozen=True)
class CityDefinition:
    city_id: str
    name: str
    osm_place: str | None = None
    osm_bbox: BBox | None = None
    is_fixture: bool = False


# west, south, east, north — UBC through Vancouver, West Van, and North Van.
VANCOUVER_BBOX: BBox = (-123.285, 49.198, -122.95, 49.375)

VANCOUVER = CityDefinition(
    city_id="vancouver",
    name="Vancouver metro",
    osm_bbox=VANCOUVER_BBOX,
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
    if city.osm_bbox is not None:
        west, south, east, north = city.osm_bbox
        return f"bbox:{west},{south},{east},{north}"
    if city.osm_place is not None:
        return city.osm_place
    return city.city_id
