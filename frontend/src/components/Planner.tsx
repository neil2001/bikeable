import { ChevronLeft, ChevronRight, LoaderCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getDefaultCityId } from "../api/client";
import { usePlanner } from "../hooks/usePlanner";
import { MapView } from "../map/MapView";
import {
  readStoredUnitSystem,
  writeStoredUnitSystem,
  type UnitSystem,
} from "../units";
import { BikeabilityLegend } from "./BikeabilityLegend";
import { RoadInspector } from "./RoadInspector";
import { RouteCharts } from "./RouteCharts";
import { RouteControls, type PanelTab } from "./RouteControls";
import { RouteSummary } from "./RouteSummary";
import { WaypointList } from "./WaypointList";

const DEFAULT_CENTER = { lat: 49.2827, lon: -123.1207 };

export function Planner() {
  const planner = usePlanner();
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [heatmapOpacity, setHeatmapOpacity] = useState(0.85);
  const [bikeabilityMin, setBikeabilityMin] = useState(0);
  const [bikeabilityMax, setBikeabilityMax] = useState(10);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [panelTab, setPanelTab] = useState<PanelTab>("plan");
  const [unitSystem, setUnitSystem] = useState<UnitSystem>(readStoredUnitSystem);

  const handleUnitSystemChange = (next: UnitSystem) => {
    setUnitSystem(next);
    writeStoredUnitSystem(next);
  };

  const mapCenter = planner.start ?? planner.waypoints[0]?.coordinate ?? DEFAULT_CENTER;
  const routeCoordinates = useMemo(() => {
    if (planner.route) {
      return [planner.route.geometry.coordinates];
    }
    return [];
  }, [planner.route]);

  const cityName =
    planner.selectedCity?.name ??
    (getDefaultCityId() === "fixture" ? "Fixture Network" : "Vancouver metro");

  const undoPlan = planner.undoPlan;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const modifier = event.metaKey || event.ctrlKey;
      if (modifier && event.key.toLowerCase() === "z" && !event.shiftKey) {
        const target = event.target as HTMLElement | null;
        if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) {
          return;
        }
        event.preventDefault();
        undoPlan();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [undoPlan]);

  return (
    <div className="planner-app">
      <div className="map-layer">
        {planner.loading || planner.heatmapLoading ? (
          <div className="map-status" role="status" aria-live="polite">
            <LoaderCircle className="spin" size={14} strokeWidth={2} aria-hidden />
            {planner.loading ? "Computing route…" : "Loading roads…"}
          </div>
        ) : null}
        <MapView
          center={mapCenter}
          cityBbox={planner.selectedCity?.bbox}
          heatmapCityId={planner.cityId}
          overlayVersion={planner.selectedCity?.overlayVersion ?? ""}
          routeCoordinates={routeCoordinates}
          waypoints={planner.waypoints}
          selectedRoadIds={planner.selectedRoadIds}
          selectedWaypointId={planner.selectedWaypointId}
          start={planner.start}
          mode={planner.mode}
          showHeatmap={showHeatmap}
          heatmapOpacity={heatmapOpacity}
          bikeabilityMin={bikeabilityMin}
          bikeabilityMax={bikeabilityMax}
          onMapClick={planner.addWaypoint}
          onRoadClick={planner.handleRoadClick}
          onMoveWaypoint={planner.moveWaypoint}
          onMoveStart={planner.setStart}
          onSelectWaypoint={planner.setSelectedWaypointId}
          onHeatmapLoadingChange={planner.setHeatmapLoading}
          onHeatmapError={planner.setHeatmapError}
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
            ? "First click drops Start; then click a road to follow it or empty map to add a stop."
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
          bikeabilityWeight={planner.bikeabilityWeight}
          setBikeabilityWeight={planner.setBikeabilityWeight}
          heatmapOpacity={heatmapOpacity}
          setHeatmapOpacity={setHeatmapOpacity}
          unitSystem={unitSystem}
          onUnitSystemChange={handleUnitSystemChange}
          targetDistanceM={planner.targetDistanceM}
          setTargetDistanceM={planner.setTargetDistanceM}
          cityId={planner.cityId}
          setCityId={planner.setCityId}
          cities={planner.cities}
          loading={planner.loading}
          onGenerate={() => void planner.generateAutoRoute()}
          onLocate={planner.useCurrentLocation}
          onExport={() => void planner.exportRoute()}
          onUndo={planner.undoPlan}
          onReturnToStart={() => void planner.returnToStart()}
          onClear={planner.clearPlan}
          canReturnToStart={planner.canReturnToStart}
          hasRoute={Boolean(planner.route)}
          hasPlan={planner.waypoints.length > 0 || planner.selectedRoadIds.length > 0}
          canUndo={planner.canUndo}
        />

        {planner.mode === "manual" ? (
          <WaypointList
            waypoints={planner.waypoints}
            selectedWaypointId={planner.selectedWaypointId}
            onSelect={planner.setSelectedWaypointId}
            onRemove={planner.removeWaypoint}
            onReorder={planner.reorderPlanWaypoints}
          />
        ) : null}

        <RouteSummary route={planner.route} unitSystem={unitSystem} />

        <RouteCharts
          route={planner.route}
          cursorDistanceM={planner.cursorDistanceM}
          onCursorChange={planner.setCursorDistanceM}
          unitSystem={unitSystem}
        />

        <RoadInspector
          inspection={planner.roadInspection}
          onClose={() => planner.setRoadInspection(null)}
          unitSystem={unitSystem}
        />
      </aside>
    </div>
  );
}
