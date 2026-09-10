import type {
  BikeabilityNetworkResponse,
  CityListResponse,
  CyclingProfile,
  HealthResponse,
  RouteResponse,
} from "../types/api";
import { parseApiResponse } from "./errors";
import { mockBikeabilityNetwork, mockCities, mockHealth, mockLoopResponse } from "./mocks/vancouver";

const apiMode = import.meta.env.VITE_API_MODE ?? "live";

export function isMockApi(): boolean {
  return apiMode === "mock";
}

export async function getHealth(): Promise<HealthResponse> {
  if (isMockApi()) {
    return mockHealth;
  }
  const response = await fetch("/api/v1/health");
  return parseApiResponse<HealthResponse>(response);
}

export async function getCities(): Promise<CityListResponse> {
  if (isMockApi()) {
    return mockCities;
  }
  const response = await fetch("/api/v1/cities");
  return parseApiResponse<CityListResponse>(response);
}

export async function getBikeabilityNetwork(
  cityId: string,
  profile: CyclingProfile = "road",
): Promise<BikeabilityNetworkResponse> {
  if (isMockApi()) {
    return mockBikeabilityNetwork;
  }
  const params = new URLSearchParams({ profile });
  const response = await fetch(`/api/v1/cities/${cityId}/bikeability?${params}`);
  return parseApiResponse<BikeabilityNetworkResponse>(response);
}

export async function generateLoop(): Promise<RouteResponse> {
  if (isMockApi()) {
    return mockLoopResponse;
  }
  const response = await fetch("/api/v1/routes/loop", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      start: { lat: 49.2827, lon: -123.1207 },
      targetDistanceM: 30000,
      profile: "road",
      preferences: { distanceWeight: 0.2, bikeabilityWeight: 0.8 },
    }),
  });
  return parseApiResponse<RouteResponse>(response);
}
