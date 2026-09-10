import type { BikeabilityNetworkResponse, CityListResponse, RouteResponse } from "../../types/api";

export const mockHealth = { status: "ok" };

export const mockCities: CityListResponse = {
  cities: [
    {
      cityId: "vancouver",
      name: "Vancouver, BC",
      bbox: {
        minLon: -123.27,
        minLat: 49.198,
        maxLon: -123.023,
        maxLat: 49.317,
      },
      graphVersion: "unbuilt",
      scoreVersion: "v1",
    },
  ],
};

export const mockLoopResponse: RouteResponse = {
  routeId: "mock-route",
  geometry: {
    type: "LineString",
    coordinates: [
      [-123.1207, 49.2827],
      [-123.134, 49.302],
      [-123.155, 49.273],
      [-123.1207, 49.2827],
    ],
  },
  distanceM: 30200,
  elevationGainM: 420,
  averageBikeability: 8.4,
  pctHighQuality: 0.92,
  pctBadRoads: 0.02,
  pctProtected: 0.3,
  highSpeedExposure: 0.01,
  hostileIntersections: 2,
  score: 8.7,
  profile: [
    { distanceM: 0, elevationM: 12, bikeability: 8.8 },
    { distanceM: 15100, elevationM: 48, bikeability: 8.1 },
    { distanceM: 30200, elevationM: 12, bikeability: 8.6 },
  ],
  scoreBreakdown: {
    averageBikeability: 8.4,
    highQualityBonus: 0.92,
    badRoadPenalty: 0.02,
    intersectionPenalty: 0.12,
    distancePenalty: 0.2,
  },
};

export const mockBikeabilityNetwork: BikeabilityNetworkResponse = {
  cityId: "vancouver",
  scoreVersion: "v1",
  features: [
    {
      type: "Feature",
      properties: { roadId: "mock-road-1", bikeability: 8.6 },
      geometry: {
        type: "LineString",
        coordinates: [
          [-123.12, 49.28],
          [-123.13, 49.29],
        ],
      },
    },
  ],
};
