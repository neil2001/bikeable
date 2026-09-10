import { useMemo } from "react";
import { getDefaultCityId } from "../api/client";
import { usePlanner } from "../hooks/usePlanner";
import { MapView } from "../map/MapView";
import { BikeabilityLegend } from "./BikeabilityLegend";
import { RoadInspector } from "./RoadInspector";
import { RouteCharts } from "./RouteCharts";
import { RouteControls } from "./RouteControls";
import { RouteSummary } from "./RouteSummary";

const DEFAULT_CENTER = { lat: 49.2827, lon: -123.1207 };

export function Planner() {
  const planner = usePlanner();
  const mapCenter = planner.start ?? planner.waypoints[0] ?? DEFAULT_CENTER;
  const routeCoordinates = useMemo(() => {
    if (planner.route) {
      return [planner.route.geometry.coordinates];
    }
    return planner.segmentGeometries;
  }, [planner.route, planner.segmentGeometries]);

  return (
    <div className="planner">
      <header className="planner-header">
        <h1>Bikeable</h1>
        <p>Map-first cycling planner for {getDefaultCityId() === "fixture" ? "Vancouver (fixture)" : "Vancouver"}.</p>
      </header>
      <div className="planner-body">
        <div className="map-panel">
          <MapView
            center={mapCenter}
            heatmapFeatures={planner.heatmapFeatures}
            routeCoordinates={routeCoordinates}
            waypoints={planner.waypoints}
            onMapClick={planner.addWaypoint}
            onRoadClick={planner.inspectRoadAt}
            cursorDistanceM={planner.cursorDistanceM}
          />
          <BikeabilityLegend />
        </div>
        <aside className="details-panel">
          {planner.error ? <p className="error">{planner.error}</p> : null}
          <RouteSummary route={planner.route} loading={planner.loading} />
          <RouteControls
            mode={planner.mode}
            setMode={planner.setMode}
            profile={planner.profile}
            setProfile={planner.setProfile}
            bikeabilityWeight={planner.bikeabilityWeight}
            setBikeabilityWeight={planner.setBikeabilityWeight}
            targetDistanceMi={planner.targetDistanceMi}
            setTargetDistanceMi={planner.setTargetDistanceMi}
            cityId={planner.cityId}
            setCityId={planner.setCityId}
            cities={planner.cities}
            loading={planner.loading}
            onGenerate={() => void planner.generateAutoRoute()}
            onLocate={planner.useCurrentLocation}
            onExport={() => void planner.exportRoute()}
            hasRoute={Boolean(planner.route)}
          />
          <RouteCharts
            route={planner.route}
            cursorDistanceM={planner.cursorDistanceM}
            onCursorChange={planner.setCursorDistanceM}
          />
          <RoadInspector
            inspection={planner.roadInspection}
            onClose={() => planner.setRoadInspection(null)}
          />
        </aside>
      </div>
    </div>
  );
}
