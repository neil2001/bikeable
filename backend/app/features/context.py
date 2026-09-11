from typing import Any

from app.features.normalize import (
    coerce_tag,
    has_cycle_network,
    normalize_highway_class,
)


def context_class(edge_data: dict[str, Any]) -> str:
    """Classify recreational / network context from OSM tags and park overlay."""
    in_park = bool(edge_data.get("in_park"))
    highway = normalize_highway_class(edge_data.get("highway"))
    foot = coerce_tag(edge_data.get("foot"))
    if in_park:
        return "park"
    if highway == "cycleway" and foot in {"yes", "designated"}:
        return "greenway"
    if has_cycle_network(edge_data):
        return "lcn"
    return "none"
