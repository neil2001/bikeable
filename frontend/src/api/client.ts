import type {
  BikeabilityNetworkResponse,
  CityListResponse,
  CyclingProfile,
  HealthResponse,
  LoopRouteRequest,
  ManualRouteRequest,
  RoadInspectionResponse,
  RouteResponse,
  SegmentRouteRequest,
  SegmentRouteResponse,
} from "../types/api";
import { parseApiResponse } from "./errors";
import {
  mockBikeabilityNetwork,
  mockCities,
  mockHealth,
  mockLoopResponse,
} from "./mocks/vancouver";

const apiMode = import.meta.env.VITE_API_MODE ?? "live";
const defaultCityId = import.meta.env.VITE_DEFAULT_CITY_ID ?? "fixture";

export function isMockApi(): boolean {
  return apiMode === "mock";
}

export function getDefaultCityId(): string {
  return defaultCityId;
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

export async function inspectRoad(
  roadId: string,
  cityId: string,
  profile: CyclingProfile = "road",
): Promise<RoadInspectionResponse> {
  const params = new URLSearchParams({ cityId, profile });
  const response = await fetch(`/api/v1/roads/${roadId}?${params}`);
  return parseApiResponse<RoadInspectionResponse>(response);
}

export async function routeSegment(
  request: SegmentRouteRequest,
  cityId: string = defaultCityId,
): Promise<SegmentRouteResponse> {
  const response = await fetch(`/api/v1/routes/segment?cityId=${cityId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseApiResponse<SegmentRouteResponse>(response);
}

export async function routeManual(
  request: ManualRouteRequest,
  cityId: string = defaultCityId,
): Promise<RouteResponse> {
  const response = await fetch(`/api/v1/routes/manual?cityId=${cityId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseApiResponse<RouteResponse>(response);
}

export async function generateLoop(
  request: LoopRouteRequest,
  cityId: string = defaultCityId,
): Promise<RouteResponse> {
  if (isMockApi()) {
    return mockLoopResponse;
  }
  const response = await fetch(`/api/v1/routes/loop?cityId=${cityId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseApiResponse<RouteResponse>(response);
}

export async function downloadGpx(routeId: string): Promise<Blob> {
  const response = await fetch(`/api/v1/routes/${routeId}/gpx`);
  if (!response.ok) {
    throw new Error("Failed to download GPX.");
  }
  return response.blob();
}
