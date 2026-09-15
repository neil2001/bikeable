from __future__ import annotations


def edge_display_name(data: dict) -> str | None:
    value = data.get("name")
    if value is None:
        return None
    items = value if isinstance(value, (list, tuple)) else [value]
    for item in items:
        text = str(item).strip()
        if text:
            return text
    return None
