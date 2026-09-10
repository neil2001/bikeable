ROAD_COMFORT_BY_HIGHWAY = {
    "living_street": 1.00,
    "residential": 1.00,
    "unclassified": 0.85,
    "service": 0.90,
    "tertiary": 0.70,
    "tertiary_link": 0.65,
    "secondary": 0.45,
    "secondary_link": 0.40,
    "primary": 0.20,
    "primary_link": 0.15,
    "trunk": 0.00,
    "trunk_link": 0.00,
    "motorway": 0.00,
    "motorway_link": 0.00,
    "cycleway": 0.95,
    "path": 0.90,
    "footway": 0.80,
    "pedestrian": 0.80,
}

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


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def infrastructure_quality(
    *,
    protected: bool,
    dedicated_path: bool,
    bike_lane: bool,
    shared_lane: bool,
    sharrow: bool,
) -> float:
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
    if highway_class is None:
        return 0.50
    return ROAD_COMFORT_BY_HIGHWAY.get(highway_class, 0.50)


def speed_comfort(speed_kph: float | None) -> float:
    if speed_kph is None:
        return 0.50
    speed_mph = speed_kph / 1.60934
    if speed_mph <= 20:
        return 1.00
    if speed_mph >= 45:
        return 0.00
    return 1.0 - (speed_mph - 20) / 25


def traffic_comfort(traffic_volume: float | None) -> float:
    if traffic_volume is None:
        return 0.50
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


def surface_quality(surface: str | None) -> float:
    if surface is None:
        return 0.50
    normalized = surface.lower().replace(" ", "_")
    if normalized in SURFACE_QUALITY:
        return SURFACE_QUALITY[normalized]
    if "asphalt" in normalized:
        return 0.70
    if "concrete" in normalized:
        return 0.90
    if "paved" in normalized:
        return 0.60
    return 0.50


def grade_comfort(grade: float | None) -> float:
    if grade is None:
        return 0.50
    absolute_grade = abs(grade)
    if absolute_grade <= 0.03:
        return 1.00
    if absolute_grade >= 0.12:
        return 0.00
    return 1.0 - (absolute_grade - 0.03) / 0.09
