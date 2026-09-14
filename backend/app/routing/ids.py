def make_road_id(source: int | str, target: int | str, key: int | str) -> str:
    return f"{source}:{target}:{key}"


def parse_road_id(road_id: str) -> tuple[int, int, int]:
    parts = road_id.split(":")
    if len(parts) != 3:
        msg = f"Invalid roadId '{road_id}'."
        raise ValueError(msg)
    return int(parts[0]), int(parts[1]), int(parts[2])


def json_osmid(value: object) -> int | list[int] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        items: list[int] = []
        seen: set[int] = set()
        for item in value:
            parsed = json_osmid(item)
            if parsed is None:
                continue
            if isinstance(parsed, list):
                for osmid in parsed:
                    if osmid not in seen:
                        seen.add(osmid)
                        items.append(osmid)
            elif parsed not in seen:
                seen.add(parsed)
                items.append(parsed)
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        return items
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
