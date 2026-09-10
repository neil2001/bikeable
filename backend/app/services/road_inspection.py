import networkx as nx
from app.features.apply import read_features_from_edge
from app.models.common import CyclingProfile
from app.models.responses import (
    BikeabilityComponents,
    RoadBikeabilityDetail,
    RoadFeatureDiagnostics,
    RoadInspectionResponse,
)
from app.routing.ids import make_road_id, parse_road_id


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
    source_node = graph.nodes[source]
    target_node = graph.nodes[target]
    return RoadInspectionResponse(
        road_id=make_road_id(source, target, key),
        geometry={
            "type": "LineString",
            "coordinates": [
                [float(source_node["lon"]), float(source_node["lat"])],
                [float(target_node["lon"]), float(target_node["lat"])],
            ],
        },
        features=RoadFeatureDiagnostics(
            highway=features.highway_class,
            speed_kph=features.speed_kph,
            lanes=edge_data.get("feat_lane_count"),
            surface=edge_data.get("surface"),
            protected_bike_infrastructure=features.protected_infrastructure,
            bike_lane=features.dedicated_bike_lane,
            grade=features.grade,
        ),
        bikeability=RoadBikeabilityDetail(
            score=float(edge_data.get("bikeability", 0.0)),
            components=BikeabilityComponents(
                infrastructure=features.infrastructure_quality,
                road_comfort=features.road_comfort,
                speed=features.speed_comfort,
                traffic=features.traffic_comfort,
                surface=features.surface_quality,
                grade=features.grade_comfort,
            ),
        ),
        profile=profile,
    )
