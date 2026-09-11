import networkx as nx
from app.graph.geometry import edge_to_wgs84_coordinates
from app.models.responses import (
    BikeabilityFeature,
    BikeabilityFeatureProperties,
    BikeabilityNetworkResponse,
)
from app.routing.ids import make_road_id


def graph_to_bikeability_response(
    graph: nx.MultiDiGraph,
    *,
    city_id: str,
    score_version: str,
) -> BikeabilityNetworkResponse:
    features: list[BikeabilityFeature] = []
    for source, target, key, edge_data in graph.edges(keys=True, data=True):
        bikeability = float(edge_data.get("bikeability", 0.0))
        coordinates = edge_to_wgs84_coordinates(graph, source, target, edge_data)
        rounded_coordinates = [
            [round(point[0], 6), round(point[1], 6)] for point in coordinates
        ]
        features.append(
            BikeabilityFeature(
                properties=BikeabilityFeatureProperties(
                    road_id=make_road_id(source, target, key),
                    bikeability=round(bikeability, 2),
                ),
                geometry={
                    "type": "LineString",
                    "coordinates": rounded_coordinates,
                },
            ),
        )
    return BikeabilityNetworkResponse(
        city_id=city_id,
        score_version=score_version,
        features=features,
    )
