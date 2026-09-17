from dataclasses import dataclass

import networkx as nx

from app.features.apply import read_features_from_edge
from app.features.mappings import (
    BUSY_HIGHWAY_CLASSES,
    EXPOSED_INFRA,
    PROTECTED_INFRA,
    infer_lane_count,
)
from app.features.model import RoadFeatures
from app.scoring.config import (
    ProfileConfig,
    ScoringConfig,
    get_profile,
    load_scoring_config,
)


def clamp(value: float, lower: float = 0.0, upper: float = 10.0) -> float:
    return max(lower, min(upper, value))


@dataclass(frozen=True)
class ScoreBreakdown:
    score: float
    base: float
    infra_bonus: float
    context_bonus: float
    interaction_delta: float
    components: dict[str, float | None]
    omitted: tuple[str, ...]
    reasons: tuple[str, ...]


def _known_base_values(features: RoadFeatures) -> dict[str, float]:
    values: dict[str, float] = {
        "traffic": features.traffic_comfort,
        "road_environment": features.road_comfort,
        "calm_geometry": features.calm_geometry,
    }
    if features.speed_comfort is not None:
        values["speed"] = features.speed_comfort
    if features.surface_quality is not None:
        values["surface"] = features.surface_quality
    if features.grade_comfort is not None:
        values["grade"] = features.grade_comfort
    return values


def _base_quality(
    features: RoadFeatures, profile: ProfileConfig
) -> tuple[float, tuple[str, ...]]:
    known = _known_base_values(features)
    weights = profile.weights.as_dict()
    weighted = 0.0
    weight_sum = 0.0
    omitted: list[str] = []
    for name, weight in weights.items():
        if weight <= 0:
            continue
        if name not in known:
            omitted.append(name)
            continue
        weighted += weight * known[name]
        weight_sum += weight
    if weight_sum <= 0:
        return 0.5, tuple(omitted)
    return weighted / weight_sum, tuple(omitted)


def _interaction_delta(
    features: RoadFeatures,
    config: ScoringConfig,
    scale: float,
) -> float:
    deltas = {term.id: term.delta for term in config.interactions}
    delta = 0.0
    busy = (features.highway_class or "") in BUSY_HIGHWAY_CLASSES
    protected = features.infra_class in PROTECTED_INFRA
    lanes = infer_lane_count(features.highway_class, features.lane_count)
    applied_protection = False

    if protected and busy:
        delta += deltas.get("protection_on_busy", 0.0)
        applied_protection = True

    speed = features.speed_comfort
    if (
        not applied_protection
        and speed is not None
        and speed <= 0.5
        and lanes >= 4
        and features.infra_class in EXPOSED_INFRA
    ):
        delta += deltas.get("fast_wide_exposed", 0.0)

    if (
        speed is not None
        and speed >= 0.9
        and features.traffic_comfort >= 0.80
        and lanes <= 2
    ):
        delta += deltas.get("calm_combo", 0.0)

    if (
        features.context_class in {"park", "greenway"}
        and speed is not None
        and speed >= 0.85
    ):
        delta += deltas.get("park_calm", 0.0)

    return clamp(delta * scale, -1.0, 1.0)


def _reasons(features: RoadFeatures) -> tuple[str, ...]:
    reasons: list[str] = []
    if features.speed_kph is not None and features.speed_kph <= 30:
        reasons.append("low speed")
    if features.traffic_comfort >= 0.75:
        if features.traffic_imputed:
            reasons.append("low traffic (estimated from road class)")
        else:
            reasons.append("low traffic")
    elif features.traffic_comfort <= 0.35:
        if features.traffic_imputed:
            reasons.append("high traffic (estimated from road class)")
        else:
            reasons.append("high traffic")
    if features.context_class == "park":
        reasons.append("park environment")
    elif features.context_class == "greenway":
        reasons.append("greenway")
    elif features.context_class == "lcn":
        reasons.append("local bike network")
    if features.oneway:
        reasons.append("one-way road")
    if features.surface_quality is not None and features.surface_quality >= 0.9:
        reasons.append("smooth pavement")
    if features.infra_class == "exclusive_cycleway":
        reasons.append("exclusive cycleway")
    elif features.infra_class == "separate_or_track":
        reasons.append("separated bike path")
    elif features.infra_class == "lane":
        reasons.append("painted bike lane")
    if features.lane_count is not None and features.lane_count <= 2:
        reasons.append("narrow roadway")
    return tuple(reasons)


def score_road_detailed(
    features: RoadFeatures,
    profile: ProfileConfig,
    *,
    config: ScoringConfig | None = None,
) -> ScoreBreakdown:
    scoring = config or load_scoring_config()
    base, omitted = _base_quality(features, profile)
    infra_points = (
        scoring.infra_bonus.get(features.infra_class, 0.0) * profile.infra_scale
    )
    context_points = (
        scoring.context_bonus.get(features.context_class, 0.0) * profile.context_scale
    )
    infra_points = min(infra_points, 2.5)
    context_points = min(context_points, 1.5)
    interaction = _interaction_delta(features, scoring, profile.interaction_scale)
    score = clamp(10.0 * base + infra_points + context_points + interaction)
    return ScoreBreakdown(
        score=score,
        base=base,
        infra_bonus=infra_points,
        context_bonus=context_points,
        interaction_delta=interaction,
        components={
            "infrastructure": features.infrastructure_quality,
            "road_comfort": features.road_comfort,
            "environment": features.road_comfort,
            "speed": features.speed_comfort,
            "traffic": features.traffic_comfort,
            "surface": features.surface_quality,
            "grade": features.grade_comfort,
            "context": context_points,
            "calm_geometry": features.calm_geometry,
        },
        omitted=omitted,
        reasons=_reasons(features),
    )


def score_road(
    features: RoadFeatures,
    profile: ProfileConfig,
    *,
    config: ScoringConfig | None = None,
) -> float:
    return score_road_detailed(features, profile, config=config).score


def score_graph(
    graph: nx.MultiDiGraph,
    *,
    config: ScoringConfig | None = None,
) -> nx.MultiDiGraph:
    scoring = config or load_scoring_config()
    profile = get_profile(scoring)

    for _source, _target, _key, edge_data in graph.edges(keys=True, data=True):
        features = read_features_from_edge(edge_data)
        breakdown = score_road_detailed(features, profile, config=scoring)
        edge_data["bikeability"] = breakdown.score
        edge_data["score_reasons"] = list(breakdown.reasons)

    graph.graph["score_version"] = str(scoring.version)
    return graph
