export type UnitSystem = "imperial" | "metric";

export const METERS_PER_MILE = 1609.34;
export const METERS_PER_FOOT = 1 / 3.28084;
export const KPH_TO_MPH = 0.621371;

export const UNIT_SYSTEM_STORAGE_KEY = "bikeable.unitSystem";

const DEFAULT_LOOP_DISTANCE_M = 30 * METERS_PER_MILE;
const LOOP_MIN_MI = 5;
const LOOP_MAX_MI = 100;
const LOOP_MIN_KM = 8;
const LOOP_MAX_KM = 161;

export function readStoredUnitSystem(): UnitSystem {
  try {
    const stored = localStorage.getItem(UNIT_SYSTEM_STORAGE_KEY);
    if (stored === "metric") {
      return "metric";
    }
  } catch {
    // ignore
  }
  return "imperial";
}

export function writeStoredUnitSystem(units: UnitSystem): void {
  try {
    localStorage.setItem(UNIT_SYSTEM_STORAGE_KEY, units);
  } catch {
    // ignore
  }
}

export function formatDistance(distanceM: number, units: UnitSystem): string {
  if (units === "metric") {
    return `${(distanceM / 1000).toFixed(1)} km`;
  }
  return `${(distanceM / METERS_PER_MILE).toFixed(1)} mi`;
}

export function formatElevation(elevationM: number, units: UnitSystem): string {
  if (units === "metric") {
    return `${Math.round(elevationM)} m`;
  }
  return `${Math.round(elevationM / METERS_PER_FOOT)} ft`;
}

export function formatSpeed(speedKph: number, units: UnitSystem): string {
  if (units === "metric") {
    return `${Math.round(speedKph)} km/h`;
  }
  return `${Math.round(speedKph * KPH_TO_MPH)} mph`;
}

export function distanceMToInput(distanceM: number, units: UnitSystem): number {
  if (units === "metric") {
    return Math.round(distanceM / 1000);
  }
  return Math.round(distanceM / METERS_PER_MILE);
}

export function inputToDistanceM(value: number, units: UnitSystem): number {
  if (units === "metric") {
    return value * 1000;
  }
  return value * METERS_PER_MILE;
}

export function loopDistanceInputMin(units: UnitSystem): number {
  return units === "metric" ? LOOP_MIN_KM : LOOP_MIN_MI;
}

export function loopDistanceInputMax(units: UnitSystem): number {
  return units === "metric" ? LOOP_MAX_KM : LOOP_MAX_MI;
}

export function defaultLoopTargetDistanceM(): number {
  return DEFAULT_LOOP_DISTANCE_M;
}

export function loopDistanceInputLabel(units: UnitSystem): string {
  return units === "metric" ? "Distance (km)" : "Distance (mi)";
}
