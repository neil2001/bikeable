from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import settings

WEIGHT_FIELDS = (
    "traffic",
    "speed",
    "road_environment",
    "surface",
    "calm_geometry",
    "grade",
)


@dataclass(frozen=True)
class BaseWeights:
    traffic: float
    speed: float
    road_environment: float
    surface: float
    calm_geometry: float
    grade: float

    def as_dict(self) -> dict[str, float]:
        return {
            "traffic": self.traffic,
            "speed": self.speed,
            "road_environment": self.road_environment,
            "surface": self.surface,
            "calm_geometry": self.calm_geometry,
            "grade": self.grade,
        }

    def as_tuple(self) -> tuple[float, ...]:
        return (
            self.traffic,
            self.speed,
            self.road_environment,
            self.surface,
            self.calm_geometry,
            self.grade,
        )


@dataclass(frozen=True)
class ProfileConfig:
    weights: BaseWeights
    infra_scale: float = 1.0
    context_scale: float = 1.0
    interaction_scale: float = 1.0


# Historical alias used by older tests/imports.
ProfileWeights = ProfileConfig


@dataclass(frozen=True)
class InteractionTerm:
    id: str
    delta: float


@dataclass(frozen=True)
class RoutingCostParams:
    gamma: float = 1.6
    avoid_score: float = 3.0
    avoid_factor: float = 1.3


@dataclass(frozen=True)
class ScoringConfig:
    version: int
    profiles: dict[str, ProfileConfig]
    infra_bonus: dict[str, float]
    context_bonus: dict[str, float]
    interactions: tuple[InteractionTerm, ...]
    routing: RoutingCostParams


def _validate_weights(profile_name: str, weights: dict[str, Any]) -> BaseWeights:
    missing = set(WEIGHT_FIELDS) - set(weights)
    if missing:
        msg = f"Profile '{profile_name}' is missing weights: {sorted(missing)}"
        raise ValueError(msg)

    parsed = BaseWeights(
        traffic=float(weights["traffic"]),
        speed=float(weights["speed"]),
        road_environment=float(weights["road_environment"]),
        surface=float(weights["surface"]),
        calm_geometry=float(weights["calm_geometry"]),
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


def _validate_profile(profile_name: str, raw: dict[str, Any]) -> ProfileConfig:
    weights = _validate_weights(profile_name, raw["weights"])
    return ProfileConfig(
        weights=weights,
        infra_scale=float(raw.get("infra_scale", 1.0)),
        context_scale=float(raw.get("context_scale", 1.0)),
        interaction_scale=float(raw.get("interaction_scale", 1.0)),
    )


def load_scoring_config(path: Path | None = None) -> ScoringConfig:
    config_path = path or settings.scoring_config_path
    raw = yaml.safe_load(config_path.read_text())
    version = int(raw["version"])
    profiles = {
        profile_name: _validate_profile(profile_name, profile)
        for profile_name, profile in raw["profiles"].items()
    }
    routing_raw = raw.get("routing") or {}
    interactions = tuple(
        InteractionTerm(id=str(item["id"]), delta=float(item["delta"]))
        for item in raw.get("interactions") or []
    )
    return ScoringConfig(
        version=version,
        profiles=profiles,
        infra_bonus={
            str(key): float(value)
            for key, value in (raw.get("infra_bonus") or {}).items()
        },
        context_bonus={
            str(key): float(value)
            for key, value in (raw.get("context_bonus") or {}).items()
        },
        interactions=interactions,
        routing=RoutingCostParams(
            gamma=float(routing_raw.get("gamma", 1.6)),
            avoid_score=float(routing_raw.get("avoid_score", 3.0)),
            avoid_factor=float(routing_raw.get("avoid_factor", 1.3)),
        ),
    )


@lru_cache(maxsize=1)
def cached_scoring_config() -> ScoringConfig:
    return load_scoring_config()


def get_profile(config: ScoringConfig | None = None) -> ProfileConfig:
    scoring = config or cached_scoring_config()
    if not scoring.profiles:
        msg = "Scoring config has no profiles."
        raise ValueError(msg)
    if len(scoring.profiles) > 1:
        msg = "Scoring config must define exactly one profile."
        raise ValueError(msg)
    return next(iter(scoring.profiles.values()))
