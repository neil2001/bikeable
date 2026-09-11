import type { StyleSpecification } from "maplibre-gl";

/**
 * Standard OpenStreetMap raster tiles — free, no API key, no watermarks.
 * Same data source as the backend OSMnx graph, so overlays align with streets.
 *
 * Usage policy: https://operations.osmfoundation.org/policies/tiles/
 * Keep attribution visible and avoid heavy bulk scraping in production.
 */
export const OSM_STANDARD_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    "osm-tiles": {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    },
  },
  layers: [
    {
      id: "osm-tiles-layer",
      type: "raster",
      source: "osm-tiles",
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};
