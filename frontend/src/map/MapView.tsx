import * as maplibregl from "maplibre-gl";
import type { FilterSpecification, LngLatBoundsLike, LngLatLike, Map, MapMouseEvent } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import {
  bikeabilityTileUrl,
  getMockBikeabilityNetwork,
  isMockApi,
} from "../api/client";
import type { Waypoint } from "../hooks/usePlanner";
import type { Coordinate } from "../types/api";
import { BIKEABILITY_STOPS, ROUTE_CASING, ROUTE_COLOR } from "./colors";
import { OPENFREEMAP_POSITRON_STYLE } from "./styles";
import { highlightRoadIds } from "./tracePath";
import "maplibre-gl/dist/maplibre-gl.css";

type Props = {
  center: Coordinate;
  cityBbox?: { minLon: number; minLat: number; maxLon: number; maxLat: number } | null;
  heatmapCityId: string;
  overlayVersion: string;
  routeCoordinates: [number, number][][];
  waypoints: Waypoint[];
  selectedRoadIds?: string[];
  selectedWaypointId?: string | null;
  start?: Coordinate | null;
  mode?: "manual" | "auto";
  showHeatmap?: boolean;
  heatmapOpacity?: number;
  bikeabilityMin?: number;
  bikeabilityMax?: number;
  onMapClick: (coordinate: Coordinate) => void;
  onRoadClick: (roadIds: string[], coordinate: Coordinate) => void;
  onMoveWaypoint?: (index: number, coordinate: Coordinate) => void;
  onMoveStart?: (coordinate: Coordinate) => void;
  onSelectWaypoint?: (id: string) => void;
  onHeatmapLoadingChange?: (loading: boolean) => void;
  onHeatmapError?: (message: string | null) => void;
  cursorDistanceM: number | null;
};

const BIKEABILITY_SOURCE = "bikeability";
const ROAD_SOURCE_LAYER = "roads";
const ROAD_LAYER = "bikeability-roads";
const TRACE_LAYER = "traced-roads";
const ROUTE_CASING_LAYER = "route-casing";
const ROUTE_LINE_LAYER = "route-line";
const CLICK_SLOP_PX = 6;
const ROAD_HIT_PAD_PX = 12;

function roadHitBox(point: { x: number; y: number }): [maplibregl.PointLike, maplibregl.PointLike] {
  return [
    [point.x - ROAD_HIT_PAD_PX, point.y - ROAD_HIT_PAD_PX],
    [point.x + ROAD_HIT_PAD_PX, point.y + ROAD_HIT_PAD_PX],
  ];
}

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

function roadIdFromFeature(feature: maplibregl.MapGeoJSONFeature): string | null {
  const roadId = feature.properties?.roadId;
  if (roadId === undefined || roadId === null) {
    return null;
  }
  return String(roadId);
}

function addBikeabilityLayers(map: Map, heatmapOpacity: number, vectorSource: boolean) {
  if (map.getLayer(ROAD_LAYER)) {
    return;
  }
  const sourceLayer = vectorSource ? { "source-layer": ROAD_SOURCE_LAYER } : {};
  map.addLayer({
    id: ROAD_LAYER,
    type: "line",
    source: BIKEABILITY_SOURCE,
    ...sourceLayer,
    layout: {
      "line-cap": "round",
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
    source: BIKEABILITY_SOURCE,
    ...sourceLayer,
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
}

function bikeabilityFilter(min: number, max: number): FilterSpecification {
  return [
    "all",
    [">=", ["get", "bikeability"], min],
    ["<=", ["get", "bikeability"], max],
  ];
}

function createWaypointElement(label: string, title: string, isStart: boolean, selected: boolean) {
  const container = document.createElement("div");
  container.className = [
    "waypoint-marker-container",
    isStart ? "start-marker" : "",
    selected ? "selected" : "",
  ]
    .filter(Boolean)
    .join(" ");

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
  overlayVersion,
  routeCoordinates,
  waypoints,
  selectedRoadIds = [],
  selectedWaypointId = null,
  start,
  mode = "manual",
  showHeatmap = true,
  heatmapOpacity = 0.8,
  bikeabilityMin = 0,
  bikeabilityMax = 10,
  onMapClick,
  onRoadClick,
  onMoveWaypoint,
  onMoveStart,
  onSelectWaypoint,
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
  const lastStartFlyRef = useRef<string>("");
  const lastSelectedFlyRef = useRef<string>("");
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
        const layers = map.getLayer(TRACE_LAYER) ? [TRACE_LAYER, ROAD_LAYER] : [ROAD_LAYER];
        const roadHits = map.queryRenderedFeatures(roadHitBox(event.point), { layers });
        const roadIds = [
          ...new Set(roadHits.map(roadIdFromFeature).filter((roadId): roadId is string => roadId !== null)),
        ];
        if (roadIds.length > 0) {
          onRoadClickRef.current(roadIds, { lat: event.lngLat.lat, lon: event.lngLat.lng });
          if (modeRef.current !== "auto") {
            return;
          }
        }
      }
      onMapClickRef.current({ lat: event.lngLat.lat, lon: event.lngLat.lng });
    });

    map.on("mouseenter", ROAD_LAYER, () => {
      if (modeRef.current !== "auto") {
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
    if (!isMockApi() && !overlayVersion) {
      return;
    }

    onHeatmapLoadingChangeRef.current?.(true);
    onHeatmapErrorRef.current?.(null);

    const finishLoading = () => {
      onHeatmapLoadingChangeRef.current?.(false);
    };

    const onIdle = () => {
      map.off("idle", onIdle);
      finishLoading();
    };

    if (isMockApi()) {
      if (!map.getSource(BIKEABILITY_SOURCE)) {
        map.addSource(BIKEABILITY_SOURCE, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
        addBikeabilityLayers(map, heatmapOpacity, false);
      }
      const source = map.getSource(BIKEABILITY_SOURCE) as maplibregl.GeoJSONSource | undefined;
      source?.setData({
        type: "FeatureCollection",
        features: getMockBikeabilityNetwork().features,
      });
      finishLoading();
      return;
    }

    const tileUrl = bikeabilityTileUrl(heatmapCityId, overlayVersion);
    const existing = map.getSource(BIKEABILITY_SOURCE) as maplibregl.VectorTileSource | undefined;
    if (existing) {
      existing.setTiles([tileUrl]);
    } else {
      map.addSource(BIKEABILITY_SOURCE, {
        type: "vector",
        tiles: [tileUrl],
        minzoom: 8,
        maxzoom: 14,
        promoteId: "roadId",
      });
      addBikeabilityLayers(map, heatmapOpacity, true);
    }
    map.once("idle", onIdle);

    return () => {
      map.off("idle", onIdle);
    };
  }, [heatmapCityId, overlayVersion, mapReady, heatmapOpacity]);

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
      if (!lastFitRouteKeyRef.current) {
        lastFitRouteKeyRef.current = "fitted";

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
    if (!map || !readyRef.current || mode !== "auto" || !start) {
      if (mode !== "auto") {
        lastStartFlyRef.current = "";
      }
      return;
    }
    const key = `${start.lat.toFixed(6)}:${start.lon.toFixed(6)}`;
    if (key === lastStartFlyRef.current) {
      return;
    }
    lastStartFlyRef.current = key;
    map.flyTo({
      center: [start.lon, start.lat] as LngLatLike,
      zoom: Math.max(map.getZoom(), 15),
      duration: 800,
    });
  }, [start, mode, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current || !selectedWaypointId) {
      return;
    }
    if (selectedWaypointId === lastSelectedFlyRef.current) {
      return;
    }
    const waypoint = waypoints.find((item) => item.id === selectedWaypointId);
    if (!waypoint) {
      return;
    }
    lastSelectedFlyRef.current = selectedWaypointId;
    map.flyTo({
      center: [waypoint.coordinate.lon, waypoint.coordinate.lat] as LngLatLike,
      zoom: Math.max(map.getZoom(), 15),
      duration: 600,
    });
  }, [selectedWaypointId, waypoints, mapReady]);

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

    if (mode === "auto" && start) {
      const { container } = createWaypointElement("S", "Start location (drag to reposition)", true, false);

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
      const selected = waypoint.id === selectedWaypointId;
      const { container } = createWaypointElement(
        String(index + 1),
        `${waypoint.label} (drag to reposition)`,
        index === 0,
        selected,
      );

      const marker = new maplibregl.Marker({
        element: container,
        anchor: "center",
        draggable: Boolean(onMoveWaypoint),
      })
        .setLngLat([waypoint.coordinate.lon, waypoint.coordinate.lat] as LngLatLike)
        .addTo(map);

      container.addEventListener("click", (event) => {
        event.stopPropagation();
        onSelectWaypoint?.(waypoint.id);
      });

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
  }, [waypoints, start, mode, mapReady, selectedWaypointId, onMoveWaypoint, onMoveStart, onSelectWaypoint]);

  return <div ref={containerRef} className="map-container" aria-label="Route map" />;
}
