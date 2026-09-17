import { Download, LocateFixed, Map as MapIcon, Route, Settings } from "lucide-react";
import type { PlannerMode } from "../hooks/usePlanner";
import type { CitySummary } from "../types/api";
import {
  distanceMToInput,
  inputToDistanceM,
  loopDistanceInputLabel,
  loopDistanceInputMax,
  loopDistanceInputMin,
  type UnitSystem,
} from "../units";

export type PanelTab = "plan" | "generate" | "settings";

type Props = {
  tab: PanelTab;
  onTabChange: (tab: PanelTab) => void;
  mode: PlannerMode;
  setMode: (mode: PlannerMode) => void;
  bikeabilityWeight: number;
  setBikeabilityWeight: (value: number) => void;
  heatmapOpacity: number;
  setHeatmapOpacity: (value: number) => void;
  unitSystem: UnitSystem;
  onUnitSystemChange: (units: UnitSystem) => void;
  targetDistanceM: number;
  setTargetDistanceM: (value: number) => void;
  cityId: string;
  setCityId: (cityId: string) => void;
  cities: CitySummary[];
  loading: boolean;
  onGenerate: () => void;
  onLocate: () => void;
  onExport: () => void;
  onUndo: () => void;
  onReturnToStart: () => void;
  onClear: () => void;
  canReturnToStart: boolean;
  hasRoute: boolean;
  hasPlan: boolean;
  canUndo: boolean;
};

export function RouteControls({
  tab,
  onTabChange,
  mode,
  setMode,
  bikeabilityWeight,
  setBikeabilityWeight,
  heatmapOpacity,
  setHeatmapOpacity,
  unitSystem,
  onUnitSystemChange,
  targetDistanceM,
  setTargetDistanceM,
  cityId,
  setCityId,
  cities,
  loading,
  onGenerate,
  onLocate,
  onExport,
  onUndo,
  onReturnToStart,
  onClear,
  canReturnToStart,
  hasRoute,
  hasPlan,
  canUndo,
}: Props) {
  return (
    <section className="controls">
      <div className="mode-toggle">
        <button
          type="button"
          className={tab === "plan" ? "active" : ""}
          onClick={() => {
            setMode("manual");
            onTabChange("plan");
          }}
        >
          <MapIcon size={16} strokeWidth={1.75} />
          Plan
        </button>
        <button
          type="button"
          className={tab === "generate" ? "active" : ""}
          onClick={() => {
            setMode("auto");
            onTabChange("generate");
          }}
        >
          <Route size={16} strokeWidth={1.75} />
          Generate
        </button>
        <button
          type="button"
          className={tab === "settings" ? "active" : ""}
          onClick={() => onTabChange("settings")}
        >
          <Settings size={16} strokeWidth={1.75} />
          Settings
        </button>
      </div>

      {tab === "settings" ? (
        <>
          <div className="unit-toggle" role="group" aria-label="Units">
            <span className="unit-toggle-label">Units</span>
            <div className="unit-toggle-buttons">
              <button
                type="button"
                className={unitSystem === "imperial" ? "active" : ""}
                aria-pressed={unitSystem === "imperial"}
                onClick={() => onUnitSystemChange("imperial")}
              >
                mi / ft
              </button>
              <button
                type="button"
                className={unitSystem === "metric" ? "active" : ""}
                aria-pressed={unitSystem === "metric"}
                onClick={() => onUnitSystemChange("metric")}
              >
                km / m
              </button>
            </div>
          </div>
          <label>
            Heatmap opacity ({Math.round(heatmapOpacity * 100)}%)
            <input
              type="range"
              min={0.2}
              max={1.0}
              step={0.05}
              value={heatmapOpacity}
              onChange={(event) => setHeatmapOpacity(Number(event.target.value))}
              aria-label="Heatmap opacity"
            />
          </label>
          <label>
            Shorter — more bikeable ({Math.round(bikeabilityWeight * 100)}%)
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={bikeabilityWeight}
              onChange={(event) => setBikeabilityWeight(Number(event.target.value))}
            />
          </label>
          <p className="hint">
            Units apply to distance, elevation, and road speed. Opacity fades the road overlay.
            Bikeable weight trades shorter paths for quieter streets.
          </p>
        </>
      ) : (
        <>
          <label>
            City
            <select value={cityId} onChange={(event) => setCityId(event.target.value)}>
              {cities.map((city) => (
                <option key={city.cityId} value={city.cityId}>
                  {city.name}
                </option>
              ))}
            </select>
          </label>
          {mode === "auto" ? (
            <>
              <label>
                {loopDistanceInputLabel(unitSystem)}
                <input
                  type="number"
                  min={loopDistanceInputMin(unitSystem)}
                  max={loopDistanceInputMax(unitSystem)}
                  value={distanceMToInput(targetDistanceM, unitSystem)}
                  onChange={(event) =>
                    setTargetDistanceM(inputToDistanceM(Number(event.target.value), unitSystem))
                  }
                />
              </label>
              <button type="button" className="primary" onClick={onGenerate} disabled={loading}>
                Generate route
              </button>
            </>
          ) : (
            <>
              <p className="hint">
                First click drops Start; then click a road to follow it or empty map to add a stop.
              </p>
              {hasPlan ? (
                <div className="btn-row">
                  <button
                    type="button"
                    className="secondary"
                    onClick={onUndo}
                    disabled={!canUndo || loading}
                  >
                    Undo last
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={onReturnToStart}
                    disabled={!canReturnToStart || loading}
                  >
                    Return to start
                  </button>
                </div>
              ) : null}
            </>
          )}
          <div className="btn-row">
            <button type="button" className="secondary" onClick={onLocate}>
              <LocateFixed size={16} strokeWidth={1.75} />
              Use my location
            </button>
            {hasRoute ? (
              <button type="button" className="secondary" onClick={onExport}>
                <Download size={16} strokeWidth={1.75} />
                Export GPX
              </button>
            ) : null}
          </div>
          {mode === "manual" ? (
            <div className="btn-row">
              <button
                type="button"
                className="secondary"
                onClick={onClear}
                disabled={!hasPlan || loading}
              >
                Clear
              </button>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
