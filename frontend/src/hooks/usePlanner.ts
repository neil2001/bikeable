import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  downloadGpx,
  generateLoop,
  getCities,
  getDefaultCityId,
  inspectRoad,
  routeManual,
  traceExtend,
} from "../api/client";
import { ApiClientError } from "../api/errors";
import { detectTraceClick } from "../map/tracePath";
import {
  applyExtensionToWaypoints,
  createWaypoint,
  isRouteClosedToStart,
  moveWaypointAt,
  removeWaypointAt,
  reorderWaypoints,
  type PlanSnapshot,
  type Waypoint,
} from "../planner/waypoints";
import { defaultLoopTargetDistanceM } from "../units";
import type {
  CitySummary,
  Coordinate,
  RoadInspectionResponse,
  RouteResponse,
} from "../types/api";

export type PlannerMode = "manual" | "auto";
export type { Waypoint };

const DEBOUNCE_MS = 350;

function cloneSnapshot(snapshot: PlanSnapshot): PlanSnapshot {
  return {
    waypoints: snapshot.waypoints.map((waypoint) => ({ ...waypoint })),
    roadIds: [...snapshot.roadIds],
    route: snapshot.route,
  };
}

export function usePlanner() {
  const [cityId, setCityId] = useState(getDefaultCityId());
  const [cities, setCities] = useState<CitySummary[]>([]);
  const [mode, setMode] = useState<PlannerMode>("manual");
  const [bikeabilityWeight, setBikeabilityWeight] = useState(0.8);
  const [targetDistanceM, setTargetDistanceM] = useState(defaultLoopTargetDistanceM);
  const [waypoints, setWaypoints] = useState<Waypoint[]>([]);
  const [selectedRoadIds, setSelectedRoadIds] = useState<string[]>([]);
  const [start, setStart] = useState<Coordinate | null>(null);
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [heatmapLoading, setHeatmapLoading] = useState(true);
  const [roadInspection, setRoadInspection] = useState<RoadInspectionResponse | null>(null);
  const [cursorDistanceM, setCursorDistanceM] = useState<number | null>(null);
  const [selectedWaypointId, setSelectedWaypointId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<number | null>(null);
  const extendInFlightRef = useRef(false);
  const historyRef = useRef<PlanSnapshot[]>([]);
  const dragSnapshotRef = useRef<PlanSnapshot | null>(null);
  const [canUndo, setCanUndo] = useState(false);

  const preferences = useMemo(
    () => ({
      distanceWeight: Number((1 - bikeabilityWeight).toFixed(2)),
      bikeabilityWeight: Number(bikeabilityWeight.toFixed(2)),
    }),
    [bikeabilityWeight],
  );

  const currentSnapshot = useCallback(
    (): PlanSnapshot => ({
      waypoints,
      roadIds: selectedRoadIds,
      route,
    }),
    [route, selectedRoadIds, waypoints],
  );

  const pushHistory = useCallback((snapshot?: PlanSnapshot) => {
    historyRef.current.push(cloneSnapshot(snapshot ?? currentSnapshot()));
    setCanUndo(true);
  }, [currentSnapshot]);

  const applySnapshot = useCallback((snapshot: PlanSnapshot) => {
    setWaypoints(snapshot.waypoints);
    setSelectedRoadIds(snapshot.roadIds);
    setRoute(snapshot.route);
    setStart(snapshot.waypoints[0]?.coordinate ?? null);
  }, []);

  const resetPlan = useCallback(() => {
    historyRef.current = [];
    setCanUndo(false);
    setWaypoints([]);
    setSelectedRoadIds([]);
    setRoute(null);
    setStart(null);
    setSelectedWaypointId(null);
    setError(null);
    setRoadInspection(null);
  }, []);

  useEffect(() => {
    void getCities().then((response) => {
      setCities(response.cities);
      setCityId((current) => {
        const selected = response.cities.find((city) => city.cityId === current);
        if (selected && selected.graphVersion !== "unbuilt") {
          return current;
        }
        const fallback = response.cities.find((city) => city.graphVersion !== "unbuilt");
        return fallback?.cityId ?? current;
      });
    });
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
      resetPlan();
    },
    [mode, resetPlan],
  );

  const changeCityId = useCallback(
    (next: string) => {
      setCityId(next);
      resetPlan();
    },
    [resetPlan],
  );

  const applyRouteResult = useCallback(
    (nextWaypoints: Waypoint[], roadIds: string[], nextRoute: RouteResponse | null) => {
      setWaypoints(nextWaypoints);
      setSelectedRoadIds(roadIds);
      setRoute(nextRoute);
      setStart(nextWaypoints[0]?.coordinate ?? null);
    },
    [],
  );

  const refreshFromWaypoints = useCallback(
    async (points: Waypoint[]) => {
      if (points.length < 2) {
        setSelectedRoadIds([]);
        setRoute(null);
        setStart(points[0]?.coordinate ?? null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const response = await routeManual(
          {
            waypoints: points.map((point) => point.coordinate),
            preferences,
          },
          cityId,
        );
        applyRouteResult(points, response.roadIds ?? [], response);
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
    [applyRouteResult, cityId, preferences],
  );

  const startCoordinate = waypoints[0]?.coordinate ?? start;

  const canReturnToStart = useMemo(() => {
    if (!startCoordinate) {
      return false;
    }
    const hasPath = selectedRoadIds.length > 0 || route !== null;
    if (!hasPath) {
      return false;
    }
    return !isRouteClosedToStart(route, startCoordinate);
  }, [route, selectedRoadIds.length, startCoordinate]);

  const returnToStart = useCallback(async () => {
    if (!canReturnToStart || !startCoordinate || extendInFlightRef.current) {
      return;
    }
    extendInFlightRef.current = true;
    setLoading(true);
    setError(null);
    const snapshot = currentSnapshot();
    try {
      const response = await traceExtend(
        {
          selectedRoadIds,
          clicked: startCoordinate,
          start: startCoordinate,
          preferences,
        },
        cityId,
      );
      pushHistory(snapshot);
      applyRouteResult(waypoints, response.roadIds, response.route);
    } catch (cause) {
      if (cause instanceof ApiClientError) {
        setError(cause.message);
      } else {
        setError("Unable to return to start.");
      }
    } finally {
      extendInFlightRef.current = false;
      setLoading(false);
    }
  }, [
    applyRouteResult,
    canReturnToStart,
    cityId,
    currentSnapshot,
    preferences,
    pushHistory,
    selectedRoadIds,
    startCoordinate,
    waypoints,
  ]);

  const extendPlan = useCallback(
    async (input: {
      clickedRoadId?: string;
      clicked: Coordinate;
      label?: string | null;
    }) => {
      if (extendInFlightRef.current) {
        return;
      }
      extendInFlightRef.current = true;
      setLoading(true);
      setError(null);
      const snapshot = currentSnapshot();
      try {
        const response = await traceExtend(
          {
            selectedRoadIds,
            clickedRoadId: input.clickedRoadId,
            clicked: input.clickedRoadId ? undefined : input.clicked,
            start: waypoints[0]?.coordinate ?? start ?? input.clicked,
            preferences,
          },
          cityId,
        );
        pushHistory(snapshot);
        const nextWaypoints = applyExtensionToWaypoints(
          waypoints,
          response.action,
          input.clicked,
          response.route,
          input.label ?? response.destinationName,
        );
        applyRouteResult(nextWaypoints, response.roadIds, response.route);
      } catch (cause) {
        if (cause instanceof ApiClientError) {
          setError(cause.message);
        } else {
          setError("Unable to extend path.");
        }
      } finally {
        extendInFlightRef.current = false;
        setLoading(false);
      }
    },
    [
      applyRouteResult,
      cityId,
      currentSnapshot,
      preferences,
      pushHistory,
      selectedRoadIds,
      start,
      waypoints,
    ],
  );

  const addWaypoint = useCallback(
    (coordinate: Coordinate) => {
      if (mode === "auto") {
        setStart(coordinate);
        return;
      }
      if (waypoints.length === 0) {
        pushHistory();
        const origin = createWaypoint(coordinate, "Start");
        setWaypoints([origin]);
        setStart(coordinate);
        setSelectedWaypointId(origin.id);
        return;
      }
      void extendPlan({ clicked: coordinate });
    },
    [extendPlan, mode, pushHistory, waypoints.length],
  );

  const moveWaypoint = useCallback(
    (index: number, coordinate: Coordinate) => {
      if (!dragSnapshotRef.current) {
        dragSnapshotRef.current = cloneSnapshot(currentSnapshot());
      }
      const next = moveWaypointAt(waypoints, index, coordinate);
      setWaypoints(next);
      setStart(next[0]?.coordinate ?? null);
      if (debounceRef.current) {
        window.clearTimeout(debounceRef.current);
      }
      debounceRef.current = window.setTimeout(() => {
        if (dragSnapshotRef.current) {
          pushHistory(dragSnapshotRef.current);
          dragSnapshotRef.current = null;
        }
        void refreshFromWaypoints(next);
      }, DEBOUNCE_MS);
    },
    [currentSnapshot, pushHistory, refreshFromWaypoints, waypoints],
  );

  const removeWaypoint = useCallback(
    (index: number) => {
      pushHistory();
      const next = removeWaypointAt(waypoints, index);
      setWaypoints(next);
      setSelectedWaypointId(next[index]?.id ?? next[next.length - 1]?.id ?? null);
      void refreshFromWaypoints(next);
    },
    [pushHistory, refreshFromWaypoints, waypoints],
  );

  const reorderPlanWaypoints = useCallback(
    (from: number, to: number) => {
      const next = reorderWaypoints(waypoints, from, to);
      if (next === waypoints) {
        return;
      }
      pushHistory();
      setWaypoints(next);
      void refreshFromWaypoints(next);
    },
    [pushHistory, refreshFromWaypoints, waypoints],
  );

  const generateAutoRoute = useCallback(async () => {
    if (!start) {
      setError("Choose a start location on the map.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await generateLoop(
        {
          start,
          targetDistanceM,
          preferences,
          constraints: {
            minDistanceM: targetDistanceM * 0.85,
            maxDistanceM: targetDistanceM * 1.15,
          },
        },
        cityId,
      );
      setRoute(response);
      setWaypoints([]);
      setSelectedRoadIds(response.roadIds ?? []);
    } catch (cause) {
      if (cause instanceof ApiClientError) {
        setError(cause.message);
      } else {
        setError("Unable to generate route.");
      }
    } finally {
      setLoading(false);
    }
  }, [cityId, preferences, start, targetDistanceM]);

  const inspectRoadAt = useCallback(
    async (roadId: string) => {
      try {
        const inspection = await inspectRoad(roadId, cityId);
        setRoadInspection(inspection);
        return inspection;
      } catch {
        setRoadInspection(null);
        return null;
      }
    },
    [cityId],
  );

  const handleRoadClick = useCallback(
    (roadIds: string[], coordinate: Coordinate) => {
      const inspectId = roadIds[0];
      if (inspectId) {
        void inspectRoadAt(inspectId);
      }
      if (mode !== "manual") {
        return;
      }
      if (waypoints.length === 0) {
        pushHistory();
        const origin = createWaypoint(coordinate, "Start");
        setWaypoints([origin]);
        setStart(coordinate);
        setSelectedWaypointId(origin.id);
        return;
      }
      const action = detectTraceClick(selectedRoadIds, roadIds);
      if (action === "noop" || extendInFlightRef.current) {
        return;
      }
      if (action === "undo-last") {
        const previous = historyRef.current.pop();
        setCanUndo(historyRef.current.length > 0);
        if (previous) {
          applySnapshot(previous);
          setError(null);
        }
        return;
      }
      setLoading(true);
      void extendPlan({
        clickedRoadId: inspectId,
        clicked: coordinate,
      });
    },
    [applySnapshot, extendPlan, inspectRoadAt, mode, pushHistory, selectedRoadIds, waypoints.length],
  );

  const undoPlan = useCallback(() => {
    const previous = historyRef.current.pop();
    setCanUndo(historyRef.current.length > 0);
    if (!previous) {
      return;
    }
    applySnapshot(previous);
    setError(null);
  }, [applySnapshot]);

  const clearPlan = useCallback(() => {
    pushHistory();
    setWaypoints([]);
    setSelectedRoadIds([]);
    setRoute(null);
    setStart(null);
    setSelectedWaypointId(null);
    setError(null);
    setRoadInspection(null);
  }, [pushHistory]);

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
          pushHistory();
          const origin = createWaypoint(coordinate, "Start");
          setWaypoints([origin]);
          setSelectedRoadIds([]);
          setRoute(null);
          setSelectedWaypointId(origin.id);
          setError(null);
        }
      },
      () => setError("Unable to access your location."),
    );
  }, [mode, pushHistory]);

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
    bikeabilityWeight,
    setBikeabilityWeight,
    targetDistanceM,
    setTargetDistanceM,
    waypoints,
    selectedRoadIds,
    selectedWaypointId,
    setSelectedWaypointId,
    start,
    setStart,
    route,
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
    reorderPlanWaypoints,
    generateAutoRoute,
    inspectRoadAt,
    handleRoadClick,
    undoPlan,
    clearPlan,
    canUndo,
    returnToStart,
    canReturnToStart,
    useCurrentLocation,
    exportRoute,
    selectedCity: cities.find((city) => city.cityId === cityId) ?? null,
  };
}
