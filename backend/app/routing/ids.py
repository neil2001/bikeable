def make_road_id(source: int | str, target: int | str, key: int | str) -> str:
    return f"{source}:{target}:{key}"


def parse_road_id(road_id: str) -> tuple[int, int, int]:
    parts = road_id.split(":")
    if len(parts) != 3:
        msg = f"Invalid roadId '{road_id}'."
        raise ValueError(msg)
    return int(parts[0]), int(parts[1]), int(parts[2])
