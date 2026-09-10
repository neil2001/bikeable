import re
from typing import Any

MPH_TO_KPH = 1.60934

PROTECTED_CYCLEWAY_VALUES = {
    "track",
    "opposite_track",
    "separate",
    "buffer",
}
DEDICATED_PATH_HIGHWAYS = {"cycleway", "path", "footway", "pedestrian"}
BIKE_LANE_VALUES = {"lane", "opposite_lane"}
SHARED_LANE_VALUES = {"share_busway", "shared_lane"}
SHARROW_VALUES = {"shared_lane", "sharrow"}


def coerce_tag(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        return coerce_tag(value[0])
    text = str(value).strip()
    return text or None


def normalize_highway_class(value: Any) -> str | None:
    text = coerce_tag(value)
    if text is None:
        return None
    if ";" in text:
        parts = [part.strip() for part in text.split(";") if part.strip()]
        return parts[0] if parts else None
    return text


def normalize_speed_kph(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).lower().strip()
    if not text or text in {"signals", "variable", "none", "unknown"}:
        return None

    mph_match = re.search(r"([\d.]+)\s*mph", text)
    if mph_match:
        return float(mph_match.group(1)) * MPH_TO_KPH

    kph_match = re.search(r"([\d.]+)\s*km/h", text)
    if kph_match:
        return float(kph_match.group(1))

    numeric_match = re.fullmatch(r"[\d.]+", text)
    if numeric_match:
        return float(text)

    return None


def normalize_lane_count(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    parts = re.findall(r"\d+", str(value))
    if not parts:
        return None
    return max(int(part) for part in parts)


def normalize_surface(value: Any) -> str | None:
    return coerce_tag(value)


def normalize_bicycle_access(value: Any) -> str | None:
    return coerce_tag(value)


def collect_cycleway_tags(edge_data: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for key, value in edge_data.items():
        if key == "cycleway" or key.startswith("cycleway:"):
            tag = coerce_tag(value)
            if tag is not None:
                tags.append(tag.lower())
    return tags


def has_protected_infrastructure(edge_data: dict[str, Any]) -> bool:
    highway = normalize_highway_class(edge_data.get("highway"))
    if highway == "cycleway":
        cycleway = coerce_tag(edge_data.get("cycleway"))
        if cycleway is None or cycleway.lower() in PROTECTED_CYCLEWAY_VALUES:
            return True

    return any(
        tag in PROTECTED_CYCLEWAY_VALUES for tag in collect_cycleway_tags(edge_data)
    )


def has_dedicated_bike_path(edge_data: dict[str, Any]) -> bool:
    highway = normalize_highway_class(edge_data.get("highway"))
    if highway in DEDICATED_PATH_HIGHWAYS:
        bicycle = normalize_bicycle_access(edge_data.get("bicycle"))
        if bicycle not in {"no", "dismount"}:
            return True

    bicycle = normalize_bicycle_access(edge_data.get("bicycle"))
    return bicycle == "designated"


def has_bike_lane(edge_data: dict[str, Any]) -> bool:
    return any(tag in BIKE_LANE_VALUES for tag in collect_cycleway_tags(edge_data))


def has_shared_lane(edge_data: dict[str, Any]) -> bool:
    tags = collect_cycleway_tags(edge_data)
    if any(tag in SHARED_LANE_VALUES for tag in tags):
        return True
    return coerce_tag(edge_data.get("cycleway")) == "shared_lane"


def has_sharrow(edge_data: dict[str, Any]) -> bool:
    return any(tag in SHARROW_VALUES for tag in collect_cycleway_tags(edge_data))


def is_traversable(edge_data: dict[str, Any]) -> bool:
    highway = normalize_highway_class(edge_data.get("highway"))
    if highway in {"motorway", "motorway_link"}:
        return False

    bicycle = normalize_bicycle_access(edge_data.get("bicycle"))
    if bicycle == "no":
        return False

    access = coerce_tag(edge_data.get("access"))
    if access == "private":
        return False

    return True
