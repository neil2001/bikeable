import * as maplibregl from "maplibre-gl";
import type { LngLatLike, Map, MapMouseEvent } from "maplibre-gl";
import { useEffect, useRef } from "react";
import type { BikeabilityFeature, Coordinate } from "../types/api";
import { bikeabilityColor } from "./colors";
import "maplibre-gl/dist/maplibre-gl.css";

type Props = {
  center: Coordinate;
  heatmapFeatures: BikeabilityFeature[];
  routeCoordinates: [number, number][][];
  waypoints: Coordinate[];
  onMapClick: (coordinate: Coordinate) => void;
  onRoadClick: (roadId: string) => void;
  cursorDistanceM: number | null;
};

const ROAD_LAYER = "bikeability-roads";

export function MapView({
  center,
  heatmapFeatures,
  routeCoordinates,
  waypoints,
  onMapClick,
  onRoadClick,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const readyRef = useRef(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return;
    }
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: "https://demotiles.maplibre.org/style.json",
      center: [center.lon, center.lat],
      zoom: 13,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
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
          "line-width": 4,
        },
      });
      map.addSource("route", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        paint: { "line-color": "#111827", "line-width": 5 },
      });
    });
    map.on("click", ROAD_LAYER, (event) => {
      const features = (event as MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }).features;
      const roadId = features?.[0]?.properties?.roadId;
      if (typeof roadId === "string") {
        onRoadClick(roadId);
      }
    });
    map.on("click", (event: MapMouseEvent) => {
      onMapClick({ lat: event.lngLat.lat, lon: event.lngLat.lng });
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      readyRef.current = false;
    };
  }, [center.lat, center.lon, onMapClick, onRoadClick]);

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
    if (!map || !readyRef.current) {
      return;
    }
    const source = map.getSource("route") as maplibregl.GeoJSONSource | undefined;
    source?.setData({
      type: "FeatureCollection",
      features: routeCoordinates.map((coordinates) => ({
        type: "Feature",
        properties: {},
        geometry: { type: "LineString", coordinates },
      })),
    });
  }, [routeCoordinates]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }
    document.querySelectorAll(".waypoint-marker").forEach((marker) => marker.remove());
    waypoints.forEach((waypoint, index) => {
      const element = document.createElement("button");
      element.className = "waypoint-marker";
      element.textContent = String(index + 1);
      element.type = "button";
      new maplibregl.Marker({ element })
        .setLngLat([waypoint.lon, waypoint.lat] as LngLatLike)
        .addTo(map);
    });
  }, [waypoints]);

  return <div ref={containerRef} className="map-container" aria-label="Route map" />;
}
