import type { BikeabilityNetworkResponse, CityListResponse, RouteResponse } from "../../types/api";

export const mockHealth = { status: "ok" };

export const mockCities: CityListResponse = {
  cities: [
    {
      cityId: "fixture",
      name: "Fixture Network",
      bbox: {
        minLon: -123.13,
        minLat: 49.278,
        maxLon: -123.09,
        maxLat: 49.283,
      },
      graphVersion: "1",
      scoreVersion: "2",
      overlayVersion: "g1-s2-o11",
    },
    {
      cityId: "vancouver",
      name: "Vancouver metro",
      bbox: {
        minLon: -123.285,
        minLat: 49.198,
        maxLon: -122.95,
        maxLat: 49.375,
      },
      graphVersion: "unbuilt",
      scoreVersion: "2",
      overlayVersion: "g1-s2-o11",
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
  scoreVersion: "2",
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
