import type { Coordinate, RouteResponse, TraceExtendAction } from "../types/api";

export type Waypoint = {
  id: string;
  coordinate: Coordinate;
  label: string;
};

export type PlanSnapshot = {
  waypoints: Waypoint[];
  roadIds: string[];
  route: RouteResponse | null;
};

const EARTH_RADIUS_M = 6371000;
const ROUTE_CLOSED_THRESHOLD_M = 28;

function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180;
}

export function distanceMeters(a: Coordinate, b: Coordinate): number {
  const dLat = toRadians(b.lat - a.lat);
  const dLon = toRadians(b.lon - a.lon);
  const lat1 = toRadians(a.lat);
  const lat2 = toRadians(b.lat);
  const sinDLat = Math.sin(dLat / 2);
  const sinDLon = Math.sin(dLon / 2);
  const h = sinDLat * sinDLat + Math.cos(lat1) * Math.cos(lat2) * sinDLon * sinDLon;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function isRouteClosedToStart(
  route: RouteResponse | null,
  startCoord: Coordinate,
  thresholdM = ROUTE_CLOSED_THRESHOLD_M,
): boolean {
  const coordinates = route?.geometry.coordinates;
  if (!coordinates || coordinates.length === 0) {
    return false;
  }
  const last = coordinates[coordinates.length - 1];
  const end = { lon: last[0], lat: last[1] };
  return distanceMeters(startCoord, end) <= thresholdM;
}

export function createWaypoint(coordinate: Coordinate, label: string): Waypoint {
  const id = globalThis.crypto?.randomUUID?.() ?? `wp_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  return { id, coordinate, label };
}

export function coordinateFromRoute(
  route: RouteResponse | null,
  which: "start" | "end",
  fallback: Coordinate,
): Coordinate {
  const coordinates = route?.geometry.coordinates;
  if (!coordinates || coordinates.length === 0) {
    return fallback;
  }
  const point = which === "start" ? coordinates[0] : coordinates[coordinates.length - 1];
  return { lon: point[0], lat: point[1] };
}

export function waypointLabel(name: string | null | undefined, index: number): string {
  const trimmed = name?.trim();
  if (trimmed) {
    return trimmed;
  }
  return index === 0 ? "Start" : `Stop ${index + 1}`;
}

export function applyExtensionToWaypoints(
  waypoints: Waypoint[],
  action: TraceExtendAction,
  click: Coordinate,
  route: RouteResponse,
  name: string | null | undefined,
): Waypoint[] {
  const destination = click;
  const label = waypointLabel(name, Math.max(waypoints.length, 1));

  if (waypoints.length === 0) {
    return [
      createWaypoint(coordinateFromRoute(route, "start", click), "Start"),
      createWaypoint(destination, label),
    ];
  }

  if (action === "same_road") {
    const next = [...waypoints];
    const last = next[next.length - 1];
    next[next.length - 1] = {
      ...last,
      coordinate: destination,
      label: last.label === "Start" && next.length === 1 ? label : last.label,
    };
    if (next.length === 1) {
      next.push(createWaypoint(destination, label));
    }
    return next;
  }

  return [...waypoints, createWaypoint(destination, label)];
}

export function moveWaypointAt(waypoints: Waypoint[], index: number, coordinate: Coordinate): Waypoint[] {
  return waypoints.map((waypoint, waypointIndex) =>
    waypointIndex === index ? { ...waypoint, coordinate } : waypoint,
  );
}

export function removeWaypointAt(waypoints: Waypoint[], index: number): Waypoint[] {
  const next = waypoints.filter((_waypoint, waypointIndex) => waypointIndex !== index);
  if (next.length === 0) {
    return next;
  }
  if (index === 0) {
    return [{ ...next[0], label: next[0].label === "Start" ? "Start" : next[0].label }];
  }
  return next;
}

export function reorderWaypoints(waypoints: Waypoint[], from: number, to: number): Waypoint[] {
  if (from === to || from < 0 || to < 0 || from >= waypoints.length || to >= waypoints.length) {
    return waypoints;
  }
  const next = [...waypoints];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  if (next[0] && next[0].label !== "Start" && waypoints[0]?.label === "Start" && from === 0) {
    next[0] = { ...next[0], label: "Start" };
  }
  return next;
}
