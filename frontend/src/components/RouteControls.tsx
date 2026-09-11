import { Download, LocateFixed, Map as MapIcon, Route, Settings } from "lucide-react";
import type { PlannerMode } from "../hooks/usePlanner";
import type { CitySummary, CyclingProfile } from "../types/api";

export type PanelTab = "plan" | "generate" | "settings";

type Props = {
  tab: PanelTab;
  onTabChange: (tab: PanelTab) => void;
  mode: PlannerMode;
  setMode: (mode: PlannerMode) => void;
  profile: CyclingProfile;
  setProfile: (profile: CyclingProfile) => void;
  bikeabilityWeight: number;
  setBikeabilityWeight: (value: number) => void;
  heatmapOpacity: number;
  setHeatmapOpacity: (value: number) => void;
  targetDistanceMi: number;
  setTargetDistanceMi: (value: number) => void;
  cityId: string;
  setCityId: (cityId: string) => void;
  cities: CitySummary[];
  loading: boolean;
  onGenerate: () => void;
  onLocate: () => void;
  onExport: () => void;
  hasRoute: boolean;
};

export function RouteControls({
  tab,
  onTabChange,
  mode,
  setMode,
  profile,
  setProfile,
  bikeabilityWeight,
  setBikeabilityWeight,
  heatmapOpacity,
  setHeatmapOpacity,
  targetDistanceMi,
  setTargetDistanceMi,
  cityId,
  setCityId,
  cities,
  loading,
  onGenerate,
  onLocate,
  onExport,
  hasRoute,
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
            Opacity fades the road overlay. Bikeable weight trades shorter paths for quieter streets.
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
          <label>
            Profile
            <select
              value={profile}
              onChange={(event) => setProfile(event.target.value as CyclingProfile)}
            >
              <option value="road">Road</option>
              <option value="commuter">Commuter</option>
              <option value="leisure">Leisure</option>
            </select>
          </label>
          {mode === "auto" ? (
            <>
              <label>
                Distance (mi)
                <input
                  type="number"
                  min={5}
                  max={100}
                  value={targetDistanceMi}
                  onChange={(event) => setTargetDistanceMi(Number(event.target.value))}
                />
              </label>
              <button type="button" className="primary" onClick={onGenerate} disabled={loading}>
                {loading ? "Finding a route…" : "Generate route"}
              </button>
            </>
          ) : (
            <p className="hint">Click the map to add numbered waypoints.</p>
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
        </>
      )}
    </section>
  );
}
