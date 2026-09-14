from app.config import settings
from app.graph.registry import get_city_definition
from app.models.responses import BBox, CitySummary
from app.scoring.config import cached_scoring_config
from app.services.city_graph import city_graph_is_available

SCORE_VERSION = str(cached_scoring_config().version)

FIXTURE = CitySummary(
    city_id="fixture",
    name="Fixture Network",
    bbox=BBox(
        min_lon=-123.13,
        min_lat=49.278,
        max_lon=-123.09,
        max_lat=49.283,
    ),
    graph_version="1",
    score_version=SCORE_VERSION,
)

VANCOUVER = CitySummary(
    city_id="vancouver",
    name="Vancouver metro",
    bbox=BBox(
        min_lon=-123.285,
        min_lat=49.198,
        max_lon=-122.95,
        max_lat=49.375,
    ),
    graph_version="1" if city_graph_is_available("vancouver") else "unbuilt",
    score_version=SCORE_VERSION,
)

CITY_SUMMARIES = {
    FIXTURE.city_id: FIXTURE,
    VANCOUVER.city_id: VANCOUVER,
}


def list_city_summaries() -> list[CitySummary]:
    return [
        city
        for city in CITY_SUMMARIES.values()
        if city.city_id != "fixture"
    ]


def get_city_summary(city_id: str) -> CitySummary:
    city = CITY_SUMMARIES.get(city_id)
    if city is None:
        msg = f"Unknown city '{city_id}'."
        raise KeyError(msg)
    return city


def resolve_city_id(city_id: str | None = None) -> str:
    requested = city_id or settings.default_city_id
    if city_graph_is_available(requested):
        get_city_definition(requested)
        return requested
    if city_graph_is_available("fixture"):
        return "fixture"
    return requested
