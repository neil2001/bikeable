from typing import Any

from app.features.normalize import (
    coerce_tag,
    normalize_highway_class,
    normalize_lane_count,
)

ROAD_ENVIRONMENT_BY_HIGHWAY = {
    "living_street": 0.88,
    "residential": 0.68,
    "unclassified": 0.75,
    "service": 0.84,
    "tertiary": 0.55,
    "tertiary_link": 0.52,
    "secondary": 0.38,
    "secondary_link": 0.36,
    "primary": 0.20,
    "primary_link": 0.18,
    "trunk": 0.05,
    "trunk_link": 0.05,
    "motorway": 0.00,
    "motorway_link": 0.00,
    "cycleway": 0.98,
    "path": 0.90,
    "footway": 0.80,
    "pedestrian": 0.80,
}

# Keep the old name as an alias used by diagnostics / tests.
ROAD_COMFORT_BY_HIGHWAY = ROAD_ENVIRONMENT_BY_HIGHWAY

SURFACE_QUALITY = {
    "asphalt": 1.00,
    "paved": 1.00,
    "concrete": 0.90,
    "concrete:plates": 0.85,
    "concrete:lanes": 0.85,
    "fine_gravel": 0.55,
    "compacted": 0.55,
    "paving_stones": 0.60,
    "sett": 0.10,
    "cobblestone": 0.10,
    "gravel": 0.30,
    "dirt": 0.10,
    "ground": 0.10,
    "sand": 0.05,
    "mud": 0.05,
}

SMOOTHNESS_QUALITY = {
    "excellent": 1.00,
    "good": 0.90,
    "intermediate": 0.60,
    "bad": 0.25,
    "very_bad": 0.10,
    "horrible": 0.05,
    "very_horrible": 0.00,
    "impassable": 0.00,
}

TRAFFIC_STRESS_BY_HIGHWAY = {
    "living_street": 0.35,
    "residential": 0.62,
    "unclassified": 0.44,
    "service": 0.38,
    "tertiary": 0.58,
    "tertiary_link": 0.60,
    "secondary": 0.68,
    "secondary_link": 0.70,
    "primary": 0.80,
    "primary_link": 0.82,
    "trunk": 0.92,
    "trunk_link": 0.94,
    "motorway": 1.00,
    "motorway_link": 1.00,
    "cycleway": 0.02,
    "path": 0.08,
    "footway": 0.12,
    "pedestrian": 0.12,
}

INFRA_QUALITY = {
    "exclusive_cycleway": 1.00,
    "separate_or_track": 0.95,
    "lane": 0.60,
    "designated_or_lcn": 0.55,
    "shared": 0.35,
    "sharrow": 0.15,
    "none": 0.00,
}

LANE_CALM = {
    1: 1.00,
    2: 0.82,
    3: 0.50,
    4: 0.28,
    5: 0.15,
    6: 0.08,
}

BUSY_HIGHWAY_CLASSES = {
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "trunk",
    "trunk_link",
}

PROTECTED_INFRA = {"separate_or_track", "exclusive_cycleway"}
EXPOSED_INFRA = {"none", "sharrow"}


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def infrastructure_quality(
    *,
    protected: bool = False,
    dedicated_path: bool = False,
    bike_lane: bool = False,
    shared_lane: bool = False,
    sharrow: bool = False,
    infra_class: str | None = None,
) -> float:
    if infra_class is not None:
        return INFRA_QUALITY.get(infra_class, 0.00)
    if protected:
        return 1.00
    if dedicated_path:
        return 0.95
    if bike_lane:
        return 0.60
    if shared_lane:
        return 0.35
    if sharrow:
        return 0.15
    return 0.00


def road_comfort(highway_class: str | None) -> float:
    return road_environment(highway_class)


def road_environment(
    highway_class: str | None,
    *,
    in_park: bool = False,
    on_lcn: bool = False,
    speed_kph: float | None = None,
    lane_count: int | None = None,
) -> float:
    """Map highway class to environment comfort. Park/LCN use context bonuses."""
    del on_lcn, speed_kph, lane_count
    if highway_class is None:
        env = 0.50
    else:
        env = ROAD_ENVIRONMENT_BY_HIGHWAY.get(highway_class, 0.50)
    if in_park and highway_class in {"tertiary", "tertiary_link", "unclassified"}:
        env = max(env, 0.62)
    return env


def speed_comfort(speed_kph: float | None) -> float | None:
    if speed_kph is None:
        return None
    if speed_kph <= 30:
        return 1.00
    if speed_kph >= 70:
        return 0.00
    if speed_kph <= 50:
        return 1.0 - (speed_kph - 30) / 20 * 0.55
    return 0.45 - (speed_kph - 50) / 20 * 0.45


def traffic_comfort_from_aadt(traffic_volume: float) -> float:
    if traffic_volume < 1_000:
        return 1.00
    if traffic_volume < 3_000:
        return 0.85
    if traffic_volume < 7_500:
        return 0.65
    if traffic_volume < 15_000:
        return 0.40
    if traffic_volume < 25_000:
        return 0.20
    return 0.00


def infer_lane_count(highway_class: str | None, lane_count: int | None) -> int:
    if lane_count is not None:
        return max(1, lane_count)
    if highway_class in {"primary", "primary_link", "trunk", "trunk_link"}:
        return 4
    if highway_class in {"secondary", "secondary_link"}:
        return 3
    return 2


def traffic_stress_proxy(
    highway_class: str | None,
    *,
    lane_count: int | None,
    speed_kph: float | None,
    oneway: bool,
) -> float:
    stress = TRAFFIC_STRESS_BY_HIGHWAY.get(highway_class or "", 0.45)
    lanes = infer_lane_count(highway_class, lane_count)
    if lanes <= 1:
        stress -= 0.06
    elif lanes == 2:
        stress += 0.00
    elif lanes == 3:
        stress += 0.10
    elif lanes == 4:
        stress += 0.18
    elif lanes == 5:
        stress += 0.26
    else:
        stress += 0.34
    if speed_kph is not None:
        if speed_kph <= 30:
            stress -= 0.06
        elif speed_kph >= 70:
            stress += 0.22
        elif speed_kph >= 50:
            stress += 0.14
    if oneway and lanes <= 2:
        stress -= 0.06
    return clamp(stress)


def traffic_comfort(
    traffic_volume: float | None,
    *,
    highway_class: str | None = None,
    lane_count: int | None = None,
    speed_kph: float | None = None,
    oneway: bool = False,
) -> tuple[float, float, bool]:
    """Return (comfort, confidence, imputed). Missing AADT uses a class proxy."""
    if traffic_volume is not None:
        return traffic_comfort_from_aadt(traffic_volume), 1.0, False
    stress = traffic_stress_proxy(
        highway_class,
        lane_count=lane_count,
        speed_kph=speed_kph,
        oneway=oneway,
    )
    return 1.0 - stress, 0.4, True


def surface_quality(surface: str | None, smoothness: str | None = None) -> float | None:
    if surface is not None:
        normalized = surface.lower().replace(" ", "_")
        if normalized in SURFACE_QUALITY:
            return SURFACE_QUALITY[normalized]
        if "asphalt" in normalized:
            return 0.70
        if "concrete" in normalized:
            return 0.90
        if "paved" in normalized:
            return 0.60
        if normalized in {"unknown", "unpaved"}:
            return 0.50 if normalized == "unknown" else 0.25
    if smoothness is not None:
        key = smoothness.lower().replace(" ", "_")
        if key in SMOOTHNESS_QUALITY:
            return SMOOTHNESS_QUALITY[key]
    if surface is None and smoothness is None:
        return None
    return None


def grade_comfort(grade: float | None) -> float | None:
    if grade is None:
        return None
    absolute_grade = abs(grade)
    if absolute_grade <= 0.03:
        return 1.00
    if absolute_grade >= 0.12:
        return 0.00
    return 1.0 - (absolute_grade - 0.03) / 0.09


def junction_sparsity(
    graph: Any | None,
    source: Any | None,
    target: Any | None,
) -> float:
    if graph is None or source is None or target is None:
        return 0.70
    try:
        degree = int(graph.degree(source)) + int(graph.degree(target))
    except Exception:
        return 0.70
    if degree <= 4:
        return 1.00
    if degree >= 12:
        return 0.20
    return 1.0 - (degree - 4) / 8.0


def calm_geometry(
    *,
    highway_class: str | None,
    lane_count: int | None,
    oneway: bool,
    junction_factor: float,
) -> float:
    lanes = infer_lane_count(highway_class, lane_count)
    lane_score = LANE_CALM.get(min(lanes, 6), 0.08)
    if oneway:
        lane_score = min(1.0, lane_score + 0.12)
    return clamp(0.7 * lane_score + 0.3 * junction_factor)


def parse_lane_count(edge_data: dict[str, Any]) -> int | None:
    return normalize_lane_count(edge_data.get("lanes"))


def parse_highway(edge_data: dict[str, Any]) -> str | None:
    return normalize_highway_class(edge_data.get("highway"))


def parse_smoothness(edge_data: dict[str, Any]) -> str | None:
    return coerce_tag(edge_data.get("smoothness"))
