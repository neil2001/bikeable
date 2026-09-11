import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  downloadGpx,
  generateLoop,
  getCities,
  getDefaultCityId,
  inspectRoad,
  routeManual,
  routeSegment,
} from "../api/client";
import { ApiClientError } from "../api/errors";
import type {
  CitySummary,
  Coordinate,
  CyclingProfile,
  RoadInspectionResponse,
  RouteResponse,
} from "../types/api";

export type PlannerMode = "manual" | "auto";

const DEBOUNCE_MS = 350;

export function usePlanner() {
  const [cityId, setCityId] = useState(getDefaultCityId());
  const [cities, setCities] = useState<CitySummary[]>([]);
  const [mode, setMode] = useState<PlannerMode>("manual");
  const [profile, setProfile] = useState<CyclingProfile>("road");
  const [bikeabilityWeight, setBikeabilityWeight] = useState(0.8);
  const [targetDistanceMi, setTargetDistanceMi] = useState(30);
  const [waypoints, setWaypoints] = useState<Coordinate[]>([]);
  const [start, setStart] = useState<Coordinate | null>(null);
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [segmentGeometries, setSegmentGeometries] = useState<[number, number][][]>([]);
  const [heatmapLoading, setHeatmapLoading] = useState(true);
  const [roadInspection, setRoadInspection] = useState<RoadInspectionResponse | null>(null);
  const [cursorDistanceM, setCursorDistanceM] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<number | null>(null);

  const preferences = useMemo(
    () => ({
      distanceWeight: Number((1 - bikeabilityWeight).toFixed(2)),
      bikeabilityWeight: Number(bikeabilityWeight.toFixed(2)),
    }),
    [bikeabilityWeight],
  );

  useEffect(() => {
    void getCities().then((response) => setCities(response.cities));
  }, []);

  const setHeatmapError = useCallback((message: string | null) => {
    setError(message);
  }, []);

  const refreshManualRoute = useCallback(
    async (points: Coordinate[]) => {
      if (points.length < 2) {
        setRoute(null);
        setSegmentGeometries([]);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const geometries: [number, number][][] = [];
        for (let index = 0; index < points.length - 1; index += 1) {
          const segment = await routeSegment(
            {
              start: points[index],
              end: points[index + 1],
              profile,
              preferences,
            },
            cityId,
          );
          geometries.push(segment.geometry.coordinates);
        }
        setSegmentGeometries(geometries);
        const fullRoute = await routeManual({ waypoints: points, profile, preferences }, cityId);
        setRoute(fullRoute);
      } catch (cause) {
        if (cause instanceof ApiClientError) {
          setError(cause.message);
        } else {
          setError("Unable to calculate route.");
        }
      } finally {
        setLoading(false);
      }
    },
    [cityId, preferences, profile],
  );

  const addWaypoint = useCallback(
    (coordinate: Coordinate) => {
      if (mode === "auto") {
        setStart(coordinate);
        return;
      }
      const next = [...waypoints, coordinate];
      setWaypoints(next);
      void refreshManualRoute(next);
    },
    [mode, refreshManualRoute, waypoints],
  );

  const moveWaypoint = useCallback(
    (index: number, coordinate: Coordinate) => {
      const next = waypoints.map((point, pointIndex) =>
        pointIndex === index ? coordinate : point,
      );
      setWaypoints(next);
      if (debounceRef.current) {
        window.clearTimeout(debounceRef.current);
      }
      debounceRef.current = window.setTimeout(() => {
        void refreshManualRoute(next);
      }, DEBOUNCE_MS);
    },
    [refreshManualRoute, waypoints],
  );

  const removeWaypoint = useCallback(
    (index: number) => {
      const next = waypoints.filter((_point, pointIndex) => pointIndex !== index);
      setWaypoints(next);
      void refreshManualRoute(next);
    },
    [refreshManualRoute, waypoints],
  );

  const generateAutoRoute = useCallback(async () => {
    if (!start) {
      setError("Choose a start location on the map.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const targetDistanceM = targetDistanceMi * 1609.34;
      const response = await generateLoop(
        {
          start,
          targetDistanceM,
          profile,
          preferences,
          constraints: {
            minDistanceM: targetDistanceM * 0.85,
            maxDistanceM: targetDistanceM * 1.15,
          },
        },
        cityId,
      );
      setRoute(response);
      setSegmentGeometries([response.geometry.coordinates]);
      setWaypoints([]);
    } catch (cause) {
      if (cause instanceof ApiClientError) {
        setError(cause.message);
      } else {
        setError("Unable to generate route.");
      }
    } finally {
      setLoading(false);
    }
  }, [cityId, preferences, profile, start, targetDistanceMi]);

  const inspectRoadAt = useCallback(
    async (roadId: string) => {
      try {
        const inspection = await inspectRoad(roadId, cityId, profile);
        setRoadInspection(inspection);
      } catch {
        setRoadInspection(null);
      }
    },
    [cityId, profile],
  );

  const useCurrentLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setError("Geolocation is not available in this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const coordinate = {
          lat: position.coords.latitude,
          lon: position.coords.longitude,
        };
        setStart(coordinate);
        if (mode === "manual") {
          setWaypoints([coordinate]);
        }
      },
      () => setError("Unable to access your location."),
    );
  }, [mode]);

  const exportRoute = useCallback(async () => {
    if (!route) {
      return;
    }
    const blob = await downloadGpx(route.routeId);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${route.routeId}.gpx`;
    anchor.click();
    URL.revokeObjectURL(url);
  }, [route]);

  return {
    cityId,
    setCityId,
    cities,
    mode,
    setMode,
    profile,
    setProfile,
    bikeabilityWeight,
    setBikeabilityWeight,
    targetDistanceMi,
    setTargetDistanceMi,
    waypoints,
    start,
    setStart,
    route,
    segmentGeometries,
    heatmapLoading,
    setHeatmapLoading,
    setHeatmapError,
    roadInspection,
    setRoadInspection,
    cursorDistanceM,
    setCursorDistanceM,
    loading,
    error,
    addWaypoint,
    moveWaypoint,
    removeWaypoint,
    generateAutoRoute,
    inspectRoadAt,
    useCurrentLocation,
    exportRoute,
    selectedCity: cities.find((c) => c.cityId === cityId) ?? null,
  };
}
