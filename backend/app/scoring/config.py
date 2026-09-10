from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import settings

WEIGHT_FIELDS = (
    "infrastructure",
    "road_comfort",
    "speed",
    "traffic",
    "surface",
    "grade",
)


@dataclass(frozen=True)
class ProfileWeights:
    infrastructure: float
    road_comfort: float
    speed: float
    traffic: float
    surface: float
    grade: float

    def as_tuple(self) -> tuple[float, float, float, float, float, float]:
        return (
            self.infrastructure,
            self.road_comfort,
            self.speed,
            self.traffic,
            self.surface,
            self.grade,
        )


@dataclass(frozen=True)
class ScoringConfig:
    version: int
    profiles: dict[str, ProfileWeights]


def _validate_weights(profile_name: str, weights: dict[str, Any]) -> ProfileWeights:
    missing = set(WEIGHT_FIELDS) - set(weights)
    if missing:
        msg = f"Profile '{profile_name}' is missing weights: {sorted(missing)}"
        raise ValueError(msg)

    parsed = ProfileWeights(
        infrastructure=float(weights["infrastructure"]),
        road_comfort=float(weights["road_comfort"]),
        speed=float(weights["speed"]),
        traffic=float(weights["traffic"]),
        surface=float(weights["surface"]),
        grade=float(weights["grade"]),
    )
    values = parsed.as_tuple()
    if any(value < 0 for value in values):
        msg = f"Profile '{profile_name}' has negative weights."
        raise ValueError(msg)
    if abs(sum(values) - 1.0) > 1e-6:
        msg = f"Profile '{profile_name}' weights must sum to 1."
        raise ValueError(msg)
    return parsed


def load_scoring_config(path: Path | None = None) -> ScoringConfig:
    config_path = path or settings.scoring_config_path
    raw = yaml.safe_load(config_path.read_text())
    version = int(raw["version"])
    profiles = {
        profile_name: _validate_weights(profile_name, profile["weights"])
        for profile_name, profile in raw["profiles"].items()
    }
    return ScoringConfig(version=version, profiles=profiles)


@lru_cache(maxsize=1)
def cached_scoring_config() -> ScoringConfig:
    return load_scoring_config()


def get_profile(profile_id: str, config: ScoringConfig | None = None) -> ProfileWeights:
    scoring = config or cached_scoring_config()
    if profile_id not in scoring.profiles:
        msg = f"Unknown profile '{profile_id}'."
        raise KeyError(msg)
    return scoring.profiles[profile_id]
