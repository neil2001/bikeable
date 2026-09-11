import { Download, LocateFixed, Map as MapIcon, Route } from "lucide-react";
import type { PlannerMode } from "../hooks/usePlanner";
import type { CitySummary, CyclingProfile } from "../types/api";

type Props = {
  mode: PlannerMode;
  setMode: (mode: PlannerMode) => void;
  profile: CyclingProfile;
  setProfile: (profile: CyclingProfile) => void;
  bikeabilityWeight: number;
  setBikeabilityWeight: (value: number) => void;
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
  mode,
  setMode,
  profile,
  setProfile,
  bikeabilityWeight,
  setBikeabilityWeight,
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
          className={mode === "manual" ? "active" : ""}
          onClick={() => setMode("manual")}
        >
          <MapIcon size={16} strokeWidth={1.75} />
          Plan
        </button>
        <button
          type="button"
          className={mode === "auto" ? "active" : ""}
          onClick={() => setMode("auto")}
        >
          <Route size={16} strokeWidth={1.75} />
          Generate
        </button>
      </div>
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
    </section>
  );
}
