import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { getDefaultCityId } from "../api/client";
import { usePlanner } from "../hooks/usePlanner";
import { MapView } from "../map/MapView";
import { BikeabilityLegend } from "./BikeabilityLegend";
import { RoadInspector } from "./RoadInspector";
import { RouteCharts } from "./RouteCharts";
import { RouteControls, type PanelTab } from "./RouteControls";
import { RouteSummary } from "./RouteSummary";

const DEFAULT_CENTER = { lat: 49.2827, lon: -123.1207 };

export function Planner() {
  const planner = usePlanner();
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [heatmapOpacity, setHeatmapOpacity] = useState(0.85);
  const [bikeabilityMin, setBikeabilityMin] = useState(0);
  const [bikeabilityMax, setBikeabilityMax] = useState(10);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [panelTab, setPanelTab] = useState<PanelTab>("plan");

  const mapCenter = planner.start ?? planner.waypoints[0] ?? DEFAULT_CENTER;
  const routeCoordinates = useMemo(() => {
    if (planner.route) {
      return [planner.route.geometry.coordinates];
    }
    return planner.segmentGeometries;
  }, [planner.route, planner.segmentGeometries]);

  const cityName =
    planner.selectedCity?.name ??
    (getDefaultCityId() === "fixture" ? "Fixture Network" : "Vancouver metro");

  return (
    <div className="planner-app">
      <div className="map-layer">
        {planner.heatmapLoading ? (
          <div className="heatmap-loading" aria-live="polite">Loading roads…</div>
        ) : null}
        <MapView
          center={mapCenter}
          cityBbox={planner.selectedCity?.bbox}
          heatmapFeatures={planner.heatmapFeatures}
          routeCoordinates={routeCoordinates}
          waypoints={planner.waypoints}
          start={planner.start}
          mode={planner.mode}
          showHeatmap={showHeatmap}
          heatmapOpacity={heatmapOpacity}
          bikeabilityMin={bikeabilityMin}
          bikeabilityMax={bikeabilityMax}
          onMapClick={planner.addWaypoint}
          onRoadClick={planner.inspectRoadAt}
          onMoveWaypoint={planner.moveWaypoint}
          onRemoveWaypoint={planner.removeWaypoint}
          onMoveStart={planner.setStart}
          cursorDistanceM={planner.cursorDistanceM}
        />
        <BikeabilityLegend
          showHeatmap={showHeatmap}
          onToggleHeatmap={() => setShowHeatmap((prev) => !prev)}
          bikeabilityMin={bikeabilityMin}
          bikeabilityMax={bikeabilityMax}
          onBikeabilityMinChange={setBikeabilityMin}
          onBikeabilityMaxChange={setBikeabilityMax}
        />
      </div>

      <header className="floating-header">
        <div className="brand-group">
          <h1>Bikeable</h1>
          <span className="city-pill">{cityName}</span>
        </div>
        <p className="subtitle">
          {planner.mode === "manual"
            ? "Click to drop a waypoint. Drag the map to pan."
            : "Click a start, then generate a loop."}
        </p>
      </header>

      <button
        type="button"
        className={`panel-toggle-btn ${sidebarOpen ? "open" : "collapsed"}`}
        onClick={() => setSidebarOpen((prev) => !prev)}
        aria-label={sidebarOpen ? "Collapse route panel" : "Expand route panel"}
      >
        {sidebarOpen ? (
          <>
            Hide
            <ChevronRight size={16} strokeWidth={1.75} />
          </>
        ) : (
          <>
            <ChevronLeft size={16} strokeWidth={1.75} />
            Route
          </>
        )}
      </button>

      <aside className={`floating-panel ${sidebarOpen ? "open" : "collapsed"}`}>
        <div className="sheet-handle" onClick={() => setSidebarOpen((prev) => !prev)} />

        {planner.error ? <div className="error-banner">{planner.error}</div> : null}

        <RouteControls
          tab={panelTab}
          onTabChange={setPanelTab}
          mode={planner.mode}
          setMode={planner.setMode}
          profile={planner.profile}
          setProfile={planner.setProfile}
          bikeabilityWeight={planner.bikeabilityWeight}
          setBikeabilityWeight={planner.setBikeabilityWeight}
          heatmapOpacity={heatmapOpacity}
          setHeatmapOpacity={setHeatmapOpacity}
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

        <RouteSummary route={planner.route} loading={planner.loading} />

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
  );
}
