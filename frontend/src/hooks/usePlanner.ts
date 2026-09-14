import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  downloadGpx,
  generateLoop,
  getCities,
  getDefaultCityId,
  inspectRoad,
  routeFromRoads,
  routeManual,
  routeSegment,
  traceExtend,
} from "../api/client";
import { ApiClientError } from "../api/errors";
import {
  applyTraceExtension,
  detectTraceClick,
  flattenTraceSteps,
  type TraceStep,
} from "../map/tracePath";
import type {
  CitySummary,
  Coordinate,
  CyclingProfile,
  RoadInspectionResponse,
  RouteResponse,
} from "../types/api";

export type PlannerMode = "manual" | "auto" | "trace";

const DEBOUNCE_MS = 350;

export function usePlanner() {
  const [cityId, setCityId] = useState(getDefaultCityId());
  const [cities, setCities] = useState<CitySummary[]>([]);
  const [mode, setMode] = useState<PlannerMode>("manual");
  const [profile, setProfile] = useState<CyclingProfile>("road");
  const [bikeabilityWeight, setBikeabilityWeight] = useState(0.8);
  const [targetDistanceMi, setTargetDistanceMi] = useState(30);
  const [waypoints, setWaypoints] = useState<Coordinate[]>([]);
  const [traceSteps, setTraceSteps] = useState<TraceStep[]>([]);
  const [start, setStart] = useState<Coordinate | null>(null);
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [segmentGeometries, setSegmentGeometries] = useState<[number, number][][]>([]);
  const [heatmapLoading, setHeatmapLoading] = useState(true);
  const [roadInspection, setRoadInspection] = useState<RoadInspectionResponse | null>(null);
  const [cursorDistanceM, setCursorDistanceM] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<number | null>(null);
  const traceInFlightRef = useRef(false);

  const selectedRoadIds = useMemo(() => flattenTraceSteps(traceSteps), [traceSteps]);

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

  const changeMode = useCallback(
    (next: PlannerMode) => {
      if (next === mode) {
        return;
      }
      setMode(next);
      setTraceSteps([]);
      setRoute(null);
      setSegmentGeometries([]);
      setError(null);
      setRoadInspection(null);
      if (next !== "manual") {
        setWaypoints([]);
      }
      if (next !== "auto" && next !== "trace") {
        setStart(null);
      }
    },
    [mode],
  );

  const changeCityId = useCallback((next: string) => {
    setCityId(next);
    setTraceSteps([]);
    setRoute(null);
    setSegmentGeometries([]);
    setWaypoints([]);
    setStart(null);
    setError(null);
    setRoadInspection(null);
  }, []);

  const refreshTraceRoute = useCallback(
    async (roadIds: string[]) => {
      if (roadIds.length === 0) {
        setRoute(null);
        setSegmentGeometries([]);
        return;
      }
      setError(null);
      try {
        const response = await routeFromRoads({ roadIds, profile }, cityId);
        setRoute(response);
        setSegmentGeometries([response.geometry.coordinates]);
      } catch (cause) {
        if (cause instanceof ApiClientError) {
          setError(cause.message);
        } else {
          setError("Unable to assemble path.");
        }
      }
    },
    [cityId, profile],
  );

  const scheduleTraceRoute = useCallback(
    (roadIds: string[]) => {
      void refreshTraceRoute(roadIds);
    },
    [refreshTraceRoute],
  );
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
      if (mode === "trace") {
        return;
      }
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

  const handleRoadClick = useCallback(
    (roadIds: string[]) => {
      const inspectId = roadIds[0];
      if (inspectId) {
        void inspectRoadAt(inspectId);
      }
      if (mode !== "trace") {
        return;
      }
      const action = detectTraceClick(traceSteps, roadIds);
      if (action === "noop") {
        return;
      }
      if (action === "undo-last" || action === "undo-first") {
        const nextSteps =
          action === "undo-last" ? traceSteps.slice(0, -1) : traceSteps.slice(1);
        setTraceSteps(nextSteps);
        setError(null);
        scheduleTraceRoute(flattenTraceSteps(nextSteps));
        return;
      }
      if (traceInFlightRef.current || !inspectId) {
        return;
      }
      traceInFlightRef.current = true;
      setLoading(true);
      setError(null);
      void traceExtend(
        {
          selectedRoadIds,
          clickedRoadId: inspectId,
          start: start ?? undefined,
          profile,
          preferences,
        },
        cityId,
      )
        .then((response) => {
          setTraceSteps(applyTraceExtension(traceSteps, response.roadIds));
          setRoute(response.route);
          setSegmentGeometries([response.route.geometry.coordinates]);
        })
        .catch((cause) => {
          if (cause instanceof ApiClientError) {
            setError(cause.message);
          } else {
            setError("Unable to extend path.");
          }
        })
        .finally(() => {
          traceInFlightRef.current = false;
          setLoading(false);
        });
    },
    [
      cityId,
      inspectRoadAt,
      mode,
      preferences,
      profile,
      scheduleTraceRoute,
      selectedRoadIds,
      start,
      traceSteps,
    ],
  );

  const undoTrace = useCallback(() => {
    const nextSteps = traceSteps.slice(0, -1);
    setTraceSteps(nextSteps);
    setError(null);
    scheduleTraceRoute(flattenTraceSteps(nextSteps));
  }, [scheduleTraceRoute, traceSteps]);

  const clearTrace = useCallback(() => {
    setTraceSteps([]);
    setError(null);
    setRoadInspection(null);
    scheduleTraceRoute([]);
  }, [scheduleTraceRoute]);

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
        if (mode === "trace") {
          setTraceSteps([]);
          setRoute(null);
          setSegmentGeometries([]);
          setError(null);
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
    setCityId: changeCityId,
    cities,
    mode,
    setMode: changeMode,
    profile,
    setProfile,
    bikeabilityWeight,
    setBikeabilityWeight,
    targetDistanceMi,
    setTargetDistanceMi,
    waypoints,
    selectedRoadIds,
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
    handleRoadClick,
    undoTrace,
    clearTrace,
    useCurrentLocation,
    exportRoute,
    selectedCity: cities.find((c) => c.cityId === cityId) ?? null,
  };
}
