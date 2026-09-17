from app.features.builder import build_features
from app.scoring.config import get_profile, load_scoring_config
from app.scoring.score import score_road

NAMED_ROADS: dict[str, dict[str, object]] = {
    "seawall_cycleway": {
        "highway": "cycleway",
        "bicycle": "designated",
        "surface": "asphalt",
        "in_park": True,
        "foot": "yes",
        "length_m": 100.0,
    },
    "stanley_park_drive": {
        "highway": "tertiary",
        "maxspeed": "30",
        "oneway": "yes",
        "lanes": "2",
        "bicycle": "yes",
        "surface": "asphalt",
        "in_park": True,
        "length_m": 100.0,
    },
    "union_separate": {
        "highway": "tertiary",
        "maxspeed": "30",
        "oneway": "yes",
        "lanes": "2",
        "surface": "asphalt",
        "cycleway:right": "separate",
        "length_m": 100.0,
    },
    "balaclava_lcn": {
        "highway": "residential",
        "maxspeed": "30",
        "lanes": "2",
        "surface": "asphalt",
        "lcn": "yes",
        "length_m": 100.0,
    },
    "hornby_separate": {
        "highway": "secondary",
        "maxspeed": "50",
        "oneway": "yes",
        "lanes": "2",
        "surface": "asphalt",
        "cycleway:right": "separate",
        "length_m": 100.0,
    },
    "broadway_primary": {
        "highway": "primary",
        "maxspeed": "50",
        "lanes": "4",
        "surface": "asphalt",
        "cycleway:both": "no",
        "length_m": 100.0,
    },
    "knight_primary": {
        "highway": "primary",
        "maxspeed": "50",
        "lanes": "6",
        "surface": "asphalt",
        "length_m": 100.0,
    },
    "georgia_trunk": {
        "highway": "trunk",
        "maxspeed": "50",
        "lanes": "7",
        "surface": "asphalt",
        "length_m": 100.0,
    },
    "residential_quiet": {
        "highway": "residential",
        "maxspeed": "30",
        "lanes": "2",
        "surface": "asphalt",
        "length_m": 100.0,
    },
    "stanley_park_missing_surface": {
        "highway": "tertiary",
        "maxspeed": "30",
        "oneway": "yes",
        "lanes": "2",
        "bicycle": "yes",
        "in_park": True,
        "length_m": 100.0,
    },
}


def _score(name: str) -> float:
    config = load_scoring_config()
    features = build_features(NAMED_ROADS[name])
    return score_road(features, get_profile(config), config=config)


def test_named_vancouver_roads_land_in_qualitative_bands() -> None:
    seawall = _score("seawall_cycleway")
    park = _score("stanley_park_drive")
    union = _score("union_separate")
    balaclava = _score("balaclava_lcn")
    hornby = _score("hornby_separate")
    broadway = _score("broadway_primary")
    knight = _score("knight_primary")
    georgia = _score("georgia_trunk")

    assert 9.0 <= seawall <= 10.0, seawall
    assert 8.0 <= park <= 9.0, park
    assert 8.0 <= union <= 9.0, union
    assert 7.0 <= balaclava <= 8.0, balaclava
    assert 7.0 <= hornby <= 8.5, hornby
    assert 3.0 <= broadway <= 5.0, broadway
    assert 2.0 <= knight <= 4.0, knight
    assert 2.0 <= georgia <= 4.0, georgia
    assert park - broadway >= 2.5
    assert seawall >= park
    assert knight <= broadway


def test_quiet_residential_without_infra_is_pleasant() -> None:
    score = _score("residential_quiet")
    assert score >= 6.5, score


def test_missing_surface_does_not_sink_park_road() -> None:
    assert _score("stanley_park_missing_surface") >= 7.5


def test_missing_aadt_does_not_score_knight_as_calm() -> None:
    from app.features.builder import build_features as build

    features = build(NAMED_ROADS["knight_primary"])
    assert features.traffic_volume is None
    assert features.traffic_comfort < 0.4
