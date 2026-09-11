from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence

BATCH_SIZE = 80
REQUEST_TIMEOUT_S = 8.0
USER_AGENT = "bikeable/0.1"

_cache: dict[tuple[float, float], float | None] = {}


def lookup_elevations(
    coordinates: Sequence[tuple[float, float]],
    *,
    api_url: str,
) -> list[float | None]:
    """Return meters above sea level for each (lat, lon), or None on failure."""
    if not coordinates:
        return []

    rounded = [_quantize(lat, lon) for lat, lon in coordinates]
    missing = [coord for coord in dict.fromkeys(rounded) if coord not in _cache]
    for index in range(0, len(missing), BATCH_SIZE):
        batch = missing[index : index + BATCH_SIZE]
        fetched = _fetch_batch(batch, api_url=api_url)
        if fetched is None:
            continue
        for coord, elevation in zip(batch, fetched, strict=False):
            _cache[coord] = elevation

    return [_cache.get(coord) for coord in rounded]


def clear_elevation_cache() -> None:
    _cache.clear()


def _quantize(lat: float, lon: float) -> tuple[float, float]:
    return (round(lat, 5), round(lon, 5))


def _fetch_batch(
    batch: Sequence[tuple[float, float]],
    *,
    api_url: str,
) -> list[float | None] | None:
    query = urllib.parse.urlencode(
        {
            "latitude": ",".join(f"{lat:.5f}" for lat, _lon in batch),
            "longitude": ",".join(f"{lon:.5f}" for _lat, lon in batch),
        },
    )
    request = urllib.request.Request(
        f"{api_url}?{query}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
            payload = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None

    elevations = payload.get("elevation")
    if not isinstance(elevations, list) or len(elevations) != len(batch):
        return None

    parsed: list[float | None] = []
    for value in elevations:
        if isinstance(value, (int, float)):
            parsed.append(float(value))
        else:
            parsed.append(None)
    return parsed
