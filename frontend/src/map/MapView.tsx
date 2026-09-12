import * as maplibregl from "maplibre-gl";
import type { FilterSpecification, LngLatBoundsLike, LngLatLike, Map, MapMouseEvent } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { getBikeabilityNetwork } from "../api/client";
import { ApiClientError } from "../api/errors";
import type { Coordinate, CyclingProfile } from "../types/api";
import { BIKEABILITY_STOPS, ROUTE_CASING, ROUTE_COLOR } from "./colors";
import { createLucideX } from "./icons";
import { OPENFREEMAP_POSITRON_STYLE } from "./styles";
import { highlightRoadIds } from "./tracePath";
import "maplibre-gl/dist/maplibre-gl.css";

type Props = {
  center: Coordinate;
  cityBbox?: { minLon: number; minLat: number; maxLon: number; maxLat: number } | null;
  heatmapCityId: string;
  heatmapProfile: CyclingProfile;
  routeCoordinates: [number, number][][];
  waypoints: Coordinate[];
  selectedRoadIds?: string[];
  start?: Coordinate | null;
  mode?: "manual" | "auto" | "trace";
  showHeatmap?: boolean;
  heatmapOpacity?: number;
  bikeabilityMin?: number;
  bikeabilityMax?: number;
  onMapClick: (coordinate: Coordinate) => void;
  onRoadClick: (roadIds: string[]) => void;
  onMoveWaypoint?: (index: number, coordinate: Coordinate) => void;
  onRemoveWaypoint?: (index: number) => void;
  onMoveStart?: (coordinate: Coordinate) => void;
  onHeatmapLoadingChange?: (loading: boolean) => void;
  onHeatmapError?: (message: string | null) => void;
  cursorDistanceM: number | null;
};

const ROAD_LAYER = "bikeability-roads";
const TRACE_LAYER = "traced-roads";
const ROUTE_CASING_LAYER = "route-casing";
const ROUTE_LINE_LAYER = "route-line";
const CLICK_SLOP_PX = 6;

function heatmapColorExpression(): maplibregl.ExpressionSpecification {
  const stops: maplibregl.ExpressionSpecification = ["interpolate", ["linear"], ["get", "bikeability"]];
  for (const { score, color } of BIKEABILITY_STOPS) {
    stops.push(score, color);
  }
  return stops;
}

function heatmapOpacityExpression(opacity: number): maplibregl.ExpressionSpecification {
  const byScore = (poor: number, mid: number, good: number, top: number): maplibregl.ExpressionSpecification => [
    "interpolate",
    ["linear"],
    ["get", "bikeability"],
    0,
    poor * opacity,
    3.33,
    poor * opacity,
    5.0,
    mid * opacity,
    6.67,
    mid * opacity,
    8.3,
    good * opacity,
    10,
    top * opacity,
  ];

  return [
    "interpolate",
    ["linear"],
    ["zoom"],
    8,
    byScore(0.02, 0.12, 0.40, 0.60),
    10,
    byScore(0.05, 0.22, 0.55, 0.75),
    12,
    byScore(0.10, 0.35, 0.68, 0.86),
    14,
    byScore(0.18, 0.50, 0.80, 0.94),
    16,
    byScore(0.32, 0.68, 0.90, 1.0),
    18,
    byScore(0.48, 0.80, 0.96, 1.0),
  ];
}

function heatmapWidthExpression(): maplibregl.ExpressionSpecification {
  const byScore = (poor: number, mid: number, good: number, top: number): maplibregl.ExpressionSpecification => [
    "interpolate",
    ["linear"],
    ["get", "bikeability"],
    0,
    poor,
    3.33,
    poor,
    5.0,
    mid,
    6.67,
    mid,
    8.3,
    good,
    10,
    top,
  ];

  // Fine hairlines when zoomed out to prevent dense urban meshes from turning into solid blobs,
  // gradually expanding into street corridors when zoomed into neighborhood/street level.
  return [
    "interpolate",
    ["linear"],
    ["zoom"],
    8,
    byScore(0.12, 0.27, 0.50, 0.80),
    10,
    byScore(0.23, 0.45, 0.80, 1.25),
    12,
    byScore(0.45, 0.80, 1.35, 2.00),
    14,
    byScore(0.90, 1.58, 2.60, 3.60),
    16,
    byScore(1.92, 3.15, 4.73, 6.30),
    18,
    byScore(3.15, 5.18, 7.65, 9.90),
  ];
}

function bikeabilityFilter(min: number, max: number): FilterSpecification {
  return [
    "all",
    [">=", ["get", "bikeability"], min],
    ["<=", ["get", "bikeability"], max],
  ];
}

function createWaypointElement(label: string, title: string, isStart: boolean) {
  const container = document.createElement("div");
  container.className = isStart
    ? "waypoint-marker-container start-marker"
    : "waypoint-marker-container";

  const inner = document.createElement("div");
  inner.className = "waypoint-marker-inner";

  const badge = document.createElement("div");
  badge.className = isStart ? "waypoint-marker start" : "waypoint-marker";
  badge.textContent = label;
  badge.title = title;
  inner.appendChild(badge);
  container.appendChild(inner);

  return { container, inner };
}

export function MapView({
  center,
  cityBbox,
  heatmapCityId,
  heatmapProfile,
  routeCoordinates,
  waypoints,
  selectedRoadIds = [],
  start,
  mode = "manual",
  showHeatmap = true,
  heatmapOpacity = 0.8,
  bikeabilityMin = 0,
  bikeabilityMax = 10,
  onMapClick,
  onRoadClick,
  onMoveWaypoint,
  onRemoveWaypoint,
  onMoveStart,
  onHeatmapLoadingChange,
  onHeatmapError,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const readyRef = useRef(false);
  const [mapReady, setMapReady] = useState(false);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const lastFitRouteKeyRef = useRef<string>("");
  const lastCityRef = useRef<string>("");
  const pointerDownRef = useRef<{ x: number; y: number } | null>(null);
  const dragOccurredRef = useRef(false);
  const suppressClickRef = useRef(false);

  const onRoadClickRef = useRef(onRoadClick);
  const onMapClickRef = useRef(onMapClick);
  const modeRef = useRef(mode);
  const onHeatmapLoadingChangeRef = useRef(onHeatmapLoadingChange);
  const onHeatmapErrorRef = useRef(onHeatmapError);

  useEffect(() => {
    onRoadClickRef.current = onRoadClick;
    onMapClickRef.current = onMapClick;
    modeRef.current = mode;
    onHeatmapLoadingChangeRef.current = onHeatmapLoadingChange;
    onHeatmapErrorRef.current = onHeatmapError;
  });

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OPENFREEMAP_POSITRON_STYLE,
      center: [center.lon, center.lat],
      zoom: 13,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "bottom-right");

    const recordPointerDown = (event: { point: { x: number; y: number } }) => {
      pointerDownRef.current = { x: event.point.x, y: event.point.y };
      dragOccurredRef.current = false;
    };

    map.on("mousedown", recordPointerDown);
    map.on("touchstart", recordPointerDown);
    map.on("dragstart", () => {
      dragOccurredRef.current = true;
    });

    map.on("load", () => {
      readyRef.current = true;
      setMapReady(true);

      map.addSource("bikeability", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
        tolerance: 2,
      });

      map.addLayer({
        id: ROAD_LAYER,
        type: "line",
        source: "bikeability",
        layout: {
          "line-cap": "butt",
          "line-join": "round",
          visibility: "visible",
        },
        paint: {
          "line-color": heatmapColorExpression(),
          "line-width": heatmapWidthExpression(),
          "line-opacity": heatmapOpacityExpression(heatmapOpacity),
        },
      });

      map.addLayer({
        id: TRACE_LAYER,
        type: "line",
        source: "bikeability",
        layout: {
          "line-cap": "round",
          "line-join": "round",
          visibility: "none",
        },
        paint: {
          "line-color": ROUTE_COLOR,
          "line-width": ["interpolate", ["linear"], ["zoom"], 10, 3.5, 13, 6, 16, 9],
          "line-opacity": 0.9,
        },
        filter: ["==", ["get", "roadId"], "__none__"],
      });

      map.addSource("route", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      map.addLayer({
        id: ROUTE_CASING_LAYER,
        type: "line",
        source: "route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": ROUTE_CASING,
          "line-width": ["interpolate", ["linear"], ["zoom"], 10, 4.5, 13, 7, 16, 10],
          "line-opacity": 0.95,
        },
      });

      map.addLayer({
        id: ROUTE_LINE_LAYER,
        type: "line",
        source: "route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": ROUTE_COLOR,
          "line-width": ["interpolate", ["linear"], ["zoom"], 10, 2.5, 13, 4.8, 16, 7.5],
          "line-opacity": 1.0,
        },
      });
    });

    map.on("click", (event: MapMouseEvent) => {
      if (suppressClickRef.current) {
        suppressClickRef.current = false;
        return;
      }
      if (dragOccurredRef.current) {
        return;
      }
      const down = pointerDownRef.current;
      if (down) {
        const moved = Math.hypot(event.point.x - down.x, event.point.y - down.y);
        if (moved > CLICK_SLOP_PX) {
          return;
        }
      }
      const originalEvent = event.originalEvent;
      if ((originalEvent.target as HTMLElement | null)?.closest(".waypoint-marker-container")) {
        return;
      }
      if (map.getLayer(ROAD_LAYER)) {
        const roadHits = map.queryRenderedFeatures(event.point, { layers: [ROAD_LAYER] });
        const roadIds = [
          ...new Set(
            roadHits
              .map((feature) => feature.properties?.roadId)
              .filter((roadId): roadId is string => typeof roadId === "string"),
          ),
        ];
        if (roadIds.length > 0) {
          onRoadClickRef.current(roadIds);
          if (modeRef.current === "trace") {
            return;
          }
        }
      }
      if (modeRef.current === "trace") {
        return;
      }
      onMapClickRef.current({ lat: event.lngLat.lat, lon: event.lngLat.lng });
    });

    map.on("mouseenter", ROAD_LAYER, () => {
      if (modeRef.current === "trace") {
        map.getCanvas().style.cursor = "pointer";
      }
    });
    map.on("mouseleave", ROAD_LAYER, () => {
      map.getCanvas().style.cursor = "";
    });

    mapRef.current = map;
    (window as unknown as { __map?: maplibregl.Map }).__map = map;

    return () => {
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
      readyRef.current = false;
      setMapReady(false);
    };
    // Initial camera only; later pans come from fitBounds / user drag.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) {
      return;
    }

    let cancelled = false;
    onHeatmapLoadingChangeRef.current?.(true);
    onHeatmapErrorRef.current?.(null);

    void getBikeabilityNetwork(heatmapCityId, heatmapProfile)
      .then((network) => {
        if (cancelled) {
          return;
        }
        const source = map.getSource("bikeability") as maplibregl.GeoJSONSource | undefined;
        source?.setData({
          type: "FeatureCollection",
          features: network.features,
        });
      })
      .catch((cause: unknown) => {
        if (cancelled) {
          return;
        }
        const source = map.getSource("bikeability") as maplibregl.GeoJSONSource | undefined;
        source?.setData({ type: "FeatureCollection", features: [] });
        if (cause instanceof ApiClientError) {
          onHeatmapErrorRef.current?.(cause.message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          onHeatmapLoadingChangeRef.current?.(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [heatmapCityId, heatmapProfile, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current || !map.getLayer(ROAD_LAYER)) {
      return;
    }
    map.setLayoutProperty(ROAD_LAYER, "visibility", showHeatmap ? "visible" : "none");
    map.setPaintProperty(ROAD_LAYER, "line-opacity", heatmapOpacityExpression(heatmapOpacity));
    map.setPaintProperty(ROAD_LAYER, "line-color", heatmapColorExpression());
    map.setPaintProperty(ROAD_LAYER, "line-width", heatmapWidthExpression());
  }, [showHeatmap, heatmapOpacity, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current || !map.getLayer(ROAD_LAYER)) {
      return;
    }
    map.setFilter(ROAD_LAYER, bikeabilityFilter(bikeabilityMin, bikeabilityMax));
  }, [bikeabilityMin, bikeabilityMax, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current || !map.getLayer(TRACE_LAYER)) {
      return;
    }
    const ids = highlightRoadIds(selectedRoadIds);
    if (ids.length === 0) {
      map.setLayoutProperty(TRACE_LAYER, "visibility", "none");
      map.setFilter(TRACE_LAYER, ["==", ["get", "roadId"], "__none__"]);
      return;
    }
    map.setLayoutProperty(TRACE_LAYER, "visibility", "visible");
    map.setFilter(TRACE_LAYER, ["in", ["get", "roadId"], ["literal", ids]]);
  }, [selectedRoadIds, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) {
      return;
    }
    const source = map.getSource("route") as maplibregl.GeoJSONSource | undefined;
    const features = routeCoordinates.map((coordinates) => ({
      type: "Feature" as const,
      properties: {},
      geometry: { type: "LineString" as const, coordinates },
    }));

    source?.setData({
      type: "FeatureCollection",
      features,
    });

    const allCoords = routeCoordinates.flat();
    if (allCoords.length >= 2) {
      const routeKey = `${allCoords.length}:${allCoords[0][0]}:${allCoords[allCoords.length - 1][0]}`;
      if (routeKey !== lastFitRouteKeyRef.current) {
        lastFitRouteKeyRef.current = routeKey;

        let minLon = Infinity;
        let minLat = Infinity;
        let maxLon = -Infinity;
        let maxLat = -Infinity;

        for (const [lon, lat] of allCoords) {
          if (lon < minLon) minLon = lon;
          if (lon > maxLon) maxLon = lon;
          if (lat < minLat) minLat = lat;
          if (lat > maxLat) maxLat = lat;
        }

        map.fitBounds(
          [
            [minLon, minLat],
            [maxLon, maxLat],
          ] as LngLatBoundsLike,
          { padding: { top: 60, bottom: 60, left: 60, right: 380 }, maxZoom: 15, duration: 800 },
        );
      }
    } else {
      lastFitRouteKeyRef.current = "";
    }
  }, [routeCoordinates]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !cityBbox) {
      return;
    }
    const cityKey = `${cityBbox.minLon}:${cityBbox.minLat}:${cityBbox.maxLon}:${cityBbox.maxLat}`;
    if (cityKey !== lastCityRef.current) {
      lastCityRef.current = cityKey;
      if (routeCoordinates.length === 0) {
        map.fitBounds(
          [
            [cityBbox.minLon, cityBbox.minLat],
            [cityBbox.maxLon, cityBbox.maxLat],
          ] as LngLatBoundsLike,
          { padding: 60, maxZoom: 13, duration: 800 },
        );
      }
    }
  }, [cityBbox, routeCoordinates.length]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = [];

    const suppressFollowingClick = () => {
      suppressClickRef.current = true;
    };

    if (mode === "trace") {
      return;
    }

    if (mode === "auto" && start) {
      const { container } = createWaypointElement("S", "Start location (drag to reposition)", true);

      const marker = new maplibregl.Marker({
        element: container,
        anchor: "center",
        draggable: true,
      })
        .setLngLat([start.lon, start.lat] as LngLatLike)
        .addTo(map);

      marker.on("dragstart", suppressFollowingClick);
      marker.on("dragend", () => {
        suppressFollowingClick();
        const lngLat = marker.getLngLat();
        onMoveStart?.({ lon: lngLat.lng, lat: lngLat.lat });
      });

      markersRef.current.push(marker);
      return;
    }

    waypoints.forEach((waypoint, index) => {
      const { container, inner } = createWaypointElement(
        String(index + 1),
        `Waypoint ${index + 1} (drag to reposition)`,
        false,
      );

      if (onRemoveWaypoint) {
        const removeBtn = document.createElement("button");
        removeBtn.className = "waypoint-remove-btn";
        removeBtn.type = "button";
        removeBtn.title = `Delete waypoint ${index + 1}`;
        removeBtn.setAttribute("aria-label", `Delete waypoint ${index + 1}`);
        removeBtn.appendChild(createLucideX(12));
        const stopAndRemove = (event: Event) => {
          event.preventDefault();
          event.stopPropagation();
          onRemoveWaypoint(index);
        };
        removeBtn.addEventListener("click", stopAndRemove);
        removeBtn.addEventListener("mousedown", (event) => {
          event.stopPropagation();
        });
        removeBtn.addEventListener("touchstart", (event) => {
          event.stopPropagation();
        });
        inner.appendChild(removeBtn);
      }

      const marker = new maplibregl.Marker({
        element: container,
        anchor: "center",
        draggable: Boolean(onMoveWaypoint),
      })
        .setLngLat([waypoint.lon, waypoint.lat] as LngLatLike)
        .addTo(map);

      if (onMoveWaypoint) {
        marker.on("dragstart", suppressFollowingClick);
        marker.on("dragend", () => {
          suppressFollowingClick();
          const lngLat = marker.getLngLat();
          onMoveWaypoint(index, { lon: lngLat.lng, lat: lngLat.lat });
        });
      }

      markersRef.current.push(marker);
    });
  }, [waypoints, start, mode, onMoveWaypoint, onRemoveWaypoint, onMoveStart]);

  return <div ref={containerRef} className="map-container" aria-label="Route map" />;
}
