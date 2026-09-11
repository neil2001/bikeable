import * as maplibregl from "maplibre-gl";
import type { LngLatBoundsLike, LngLatLike, Map, MapMouseEvent } from "maplibre-gl";
import { useEffect, useRef } from "react";
import type { BikeabilityFeature, Coordinate } from "../types/api";
import { ACCENT, bikeabilityColor } from "./colors";
import { createLucideX } from "./icons";
import { OSM_STANDARD_STYLE } from "./styles";
import "maplibre-gl/dist/maplibre-gl.css";

type Props = {
  center: Coordinate;
  cityBbox?: { minLon: number; minLat: number; maxLon: number; maxLat: number } | null;
  heatmapFeatures: BikeabilityFeature[];
  routeCoordinates: [number, number][][];
  waypoints: Coordinate[];
  start?: Coordinate | null;
  mode?: "manual" | "auto";
  showHeatmap?: boolean;
  heatmapOpacity?: number;
  onMapClick: (coordinate: Coordinate) => void;
  onRoadClick: (roadId: string) => void;
  onMoveWaypoint?: (index: number, coordinate: Coordinate) => void;
  onRemoveWaypoint?: (index: number) => void;
  onMoveStart?: (coordinate: Coordinate) => void;
  cursorDistanceM: number | null;
};

const ROAD_LAYER = "bikeability-roads";
const ROUTE_CASING_LAYER = "route-casing";
const ROUTE_LINE_LAYER = "route-line";
const CLICK_SLOP_PX = 6;

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
  heatmapFeatures,
  routeCoordinates,
  waypoints,
  start,
  mode = "manual",
  showHeatmap = true,
  heatmapOpacity = 0.8,
  onMapClick,
  onRoadClick,
  onMoveWaypoint,
  onRemoveWaypoint,
  onMoveStart,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const readyRef = useRef(false);
  const pendingHeatmapRef = useRef(heatmapFeatures);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const lastFitRouteKeyRef = useRef<string>("");
  const lastCityRef = useRef<string>("");
  const pointerDownRef = useRef<{ x: number; y: number } | null>(null);
  const dragOccurredRef = useRef(false);
  const suppressClickRef = useRef(false);

  const onRoadClickRef = useRef(onRoadClick);
  const onMapClickRef = useRef(onMapClick);

  useEffect(() => {
    onRoadClickRef.current = onRoadClick;
    onMapClickRef.current = onMapClick;
  });

  useEffect(() => {
    pendingHeatmapRef.current = heatmapFeatures;
  }, [heatmapFeatures]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STANDARD_STYLE,
      center: [center.lon, center.lat],
      zoom: 13,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");

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

      map.addSource("bikeability", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      map.addLayer({
        id: ROAD_LAYER,
        type: "line",
        source: "bikeability",
        layout: {
          "line-cap": "round",
          "line-join": "round",
          visibility: "visible",
        },
        paint: {
          "line-color": [
            "interpolate",
            ["linear"],
            ["get", "bikeability"],
            0,
            bikeabilityColor(0),
            5,
            bikeabilityColor(5),
            10,
            bikeabilityColor(10),
          ],
          "line-width": ["interpolate", ["linear"], ["zoom"], 10, 1.2, 13, 2.8, 16, 5.5],
          "line-opacity": 0.85,
        },
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
          "line-color": "#ffffff",
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
          "line-color": ACCENT,
          "line-width": ["interpolate", ["linear"], ["zoom"], 10, 2.5, 13, 4.8, 16, 7.5],
          "line-opacity": 1.0,
        },
      });

      const bikeabilitySource = map.getSource("bikeability") as maplibregl.GeoJSONSource;
      bikeabilitySource.setData({
        type: "FeatureCollection",
        features: pendingHeatmapRef.current,
      });

      map.on("mouseenter", ROAD_LAYER, () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", ROAD_LAYER, () => {
        map.getCanvas().style.cursor = "";
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
        const roadId = roadHits[0]?.properties?.roadId;
        if (typeof roadId === "string") {
          onRoadClickRef.current(roadId);
          return;
        }
      }
      onMapClickRef.current({ lat: event.lngLat.lat, lon: event.lngLat.lng });
    });

    mapRef.current = map;

    return () => {
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
      readyRef.current = false;
    };
    // Initial camera only; later pans come from fitBounds / user drag.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) {
      return;
    }
    const source = map.getSource("bikeability") as maplibregl.GeoJSONSource | undefined;
    source?.setData({ type: "FeatureCollection", features: heatmapFeatures });
  }, [heatmapFeatures]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current || !map.getLayer(ROAD_LAYER)) {
      return;
    }
    map.setLayoutProperty(ROAD_LAYER, "visibility", showHeatmap ? "visible" : "none");
    map.setPaintProperty(ROAD_LAYER, "line-opacity", heatmapOpacity);
  }, [showHeatmap, heatmapOpacity]);

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
          suppressFollowingClick();
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
