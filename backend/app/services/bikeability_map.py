import networkx as nx
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
        source_node = graph.nodes[source]
        target_node = graph.nodes[target]
        bikeability = float(edge_data.get("bikeability", 0.0))
        features.append(
            BikeabilityFeature(
                properties=BikeabilityFeatureProperties(
                    road_id=make_road_id(source, target, key),
                    bikeability=round(bikeability, 2),
                ),
                geometry={
                    "type": "LineString",
                    "coordinates": [
                        [float(source_node["lon"]), float(source_node["lat"])],
                        [float(target_node["lon"]), float(target_node["lat"])],
                    ],
                },
            ),
        )
    return BikeabilityNetworkResponse(
        city_id=city_id,
        score_version=score_version,
        features=features,
    )
