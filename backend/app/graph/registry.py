from dataclasses import dataclass


@dataclass(frozen=True)
class CityDefinition:
    city_id: str
    name: str
    osm_place: str | None = None
    is_fixture: bool = False


VANCOUVER = CityDefinition(
    city_id="vancouver",
    name="Vancouver, BC",
    osm_place="Vancouver, British Columbia, Canada",
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
