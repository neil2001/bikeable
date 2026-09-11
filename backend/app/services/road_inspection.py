import networkx as nx
from app.features.apply import read_features_from_edge
from app.graph.geometry import edge_to_wgs84_coordinates
from app.models.common import CyclingProfile
from app.models.responses import (
    BikeabilityComponents,
    RoadBikeabilityDetail,
    RoadFeatureDiagnostics,
    RoadInspectionResponse,
)
from app.routing.ids import make_road_id, parse_road_id
from app.scoring.config import get_profile, load_scoring_config
from app.scoring.score import score_road_detailed


def inspect_road(
    graph: nx.MultiDiGraph,
    road_id: str,
    profile: CyclingProfile,
) -> RoadInspectionResponse:
    source, target, key = parse_road_id(road_id)
    edge_data = graph.get_edge_data(source, target, key)
    if edge_data is None:
        msg = f"Road '{road_id}' was not found."
        raise KeyError(msg)

    features = read_features_from_edge(edge_data)
    scoring = load_scoring_config()
    breakdown = score_road_detailed(
        features,
        get_profile(profile.value, scoring),
        config=scoring,
    )
    coordinates = edge_to_wgs84_coordinates(graph, source, target, edge_data)
    stored_reasons = edge_data.get("score_reasons")
    reasons = (
        [str(item) for item in stored_reasons]
        if isinstance(stored_reasons, list)
        else list(breakdown.reasons)
    )
    return RoadInspectionResponse(
        road_id=make_road_id(source, target, key),
        geometry={
            "type": "LineString",
            "coordinates": coordinates,
        },
        features=RoadFeatureDiagnostics(
            highway=features.highway_class,
            speed_kph=features.speed_kph,
            lanes=features.lane_count,
            surface=edge_data.get("surface"),
            protected_bike_infrastructure=features.protected_infrastructure,
            bike_lane=features.dedicated_bike_lane,
            grade=features.grade,
        ),
        bikeability=RoadBikeabilityDetail(
            score=float(edge_data.get("bikeability", breakdown.score)),
            components=BikeabilityComponents(
                infrastructure=features.infrastructure_quality,
                road_comfort=features.road_comfort,
                environment=features.road_comfort,
                speed=features.speed_comfort,
                traffic=features.traffic_comfort,
                surface=features.surface_quality,
                grade=features.grade_comfort,
                context=breakdown.context_bonus,
                calm_geometry=features.calm_geometry,
            ),
            reasons=reasons,
        ),
        profile=profile,
    )
