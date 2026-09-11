import re
from typing import Any

MPH_TO_KPH = 1.60934

PROTECTED_CYCLEWAY_VALUES = {
    "track",
    "opposite_track",
    "separate",
    "buffer",
}
ABSENT_CYCLEWAY_VALUES = {"no", "none", "no_lane"}
DEDICATED_PATH_HIGHWAYS = {"cycleway", "path", "footway", "pedestrian"}
BIKE_LANE_VALUES = {"lane", "opposite_lane"}
SHARED_LANE_VALUES = {"share_busway"}
SHARROW_VALUES = {"shared_lane", "sharrow"}
NETWORK_YES_VALUES = {"yes", "true", "1"}
ONEWAY_VALUES = {"yes", "true", "1", "-1"}


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


def present_cycleway_tags(edge_data: dict[str, Any]) -> list[str]:
    return [
        tag
        for tag in collect_cycleway_tags(edge_data)
        if tag not in ABSENT_CYCLEWAY_VALUES
    ]


def normalize_oneway(value: Any) -> bool:
    text = coerce_tag(value)
    if text is None:
        return False
    return text.lower() in ONEWAY_VALUES


def has_cycle_network(edge_data: dict[str, Any]) -> bool:
    for key in ("lcn", "rcn", "ncn"):
        text = coerce_tag(edge_data.get(key))
        if text is not None and text.lower() in NETWORK_YES_VALUES:
            return True
    return False


def normalize_grade(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().lower()
    if not text or text in {"up", "down", "yes"}:
        return None
    percent = re.search(r"(-?[\d.]+)\s*%", text)
    if percent:
        return float(percent.group(1)) / 100.0
    numeric = re.fullmatch(r"-?[\d.]+", text)
    if numeric:
        number = float(text)
        return number / 100.0 if abs(number) > 1 else number
    return None


def classify_infra(edge_data: dict[str, Any]) -> str:
    highway = normalize_highway_class(edge_data.get("highway"))
    bicycle = normalize_bicycle_access(edge_data.get("bicycle"))
    tags = present_cycleway_tags(edge_data)

    if highway == "cycleway":
        return "exclusive_cycleway"
    if any(tag in PROTECTED_CYCLEWAY_VALUES for tag in tags):
        return "separate_or_track"
    if any(tag in BIKE_LANE_VALUES for tag in tags):
        return "lane"
    if bicycle == "designated" or has_cycle_network(edge_data):
        return "designated_or_lcn"
    if any(tag in SHARED_LANE_VALUES for tag in tags):
        return "shared"
    if any(tag in SHARROW_VALUES for tag in tags):
        return "sharrow"
    return "none"


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

    if highway == "busway" and bicycle not in {"yes", "designated"}:
        return False

    access = coerce_tag(edge_data.get("access"))
    if access == "private":
        return False

    return True
