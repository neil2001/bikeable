import type {
  BikeabilityNetworkResponse,
  CityListResponse,
  HealthResponse,
  LoopRouteRequest,
  ManualRouteRequest,
  FromRoadsRequest,
  RoadInspectionResponse,
  RouteResponse,
  SegmentRouteRequest,
  SegmentRouteResponse,
  TraceExtendRequest,
  TraceExtendResponse,
} from "../types/api";
import { parseApiResponse } from "./errors";
import {
  mockBikeabilityNetwork,
  mockCities,
  mockHealth,
  mockLoopResponse,
} from "./mocks/vancouver";

const apiMode = import.meta.env.VITE_API_MODE ?? "live";
const defaultCityId = import.meta.env.VITE_DEFAULT_CITY_ID ?? "vancouver";

export function isMockApi(): boolean {
  return apiMode === "mock";
}

export function getDefaultCityId(): string {
  return defaultCityId;
}

export function bikeabilityTileUrl(cityId: string, overlayVersion: string): string {
  const version = encodeURIComponent(overlayVersion);
  return `/api/v1/cities/${cityId}/bikeability/tiles/{z}/{x}/{y}.pbf?v=${version}`;
}

export function getMockBikeabilityNetwork(): BikeabilityNetworkResponse {
  return mockBikeabilityNetwork;
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

export async function inspectRoad(
  roadId: string,
  cityId: string,
): Promise<RoadInspectionResponse> {
  const params = new URLSearchParams({ cityId });
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

export async function routeFromRoads(
  request: FromRoadsRequest,
  cityId: string = defaultCityId,
): Promise<RouteResponse> {
  const response = await fetch(`/api/v1/routes/from-roads?cityId=${cityId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseApiResponse<RouteResponse>(response);
}

export async function traceExtend(
  request: TraceExtendRequest,
  cityId: string = defaultCityId,
): Promise<TraceExtendResponse> {
  const response = await fetch(`/api/v1/routes/trace-extend?cityId=${cityId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseApiResponse<TraceExtendResponse>(response);
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
