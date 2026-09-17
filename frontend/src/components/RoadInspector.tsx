import { X } from "lucide-react";
import type { RoadInspectionResponse } from "../types/api";
import { formatSpeed, type UnitSystem } from "../units";

type Props = {
  inspection: RoadInspectionResponse | null;
  onClose: () => void;
  unitSystem: UnitSystem;
};

export function RoadInspector({ inspection, onClose, unitSystem }: Props) {
  if (!inspection) {
    return null;
  }

  return (
    <section className="road-inspector" aria-live="polite">
      <button type="button" className="close-button" onClick={onClose} aria-label="Close">
        <X size={16} strokeWidth={1.75} />
      </button>
      <h2>{inspection.features.name ?? "Road"}</h2>
      <p className="score-line">
        Bikeability <strong>{inspection.bikeability.score.toFixed(1)}</strong> / 10
      </p>
      <dl>
        <dt>Highway</dt>
        <dd>{inspection.features.highway ?? "unknown"}</dd>
        <dt>Speed</dt>
        <dd>
          {inspection.features.speedKph
            ? formatSpeed(inspection.features.speedKph, unitSystem)
            : "unknown"}
        </dd>
        <dt>Surface</dt>
        <dd>{inspection.features.surface ?? "unknown"}</dd>
        <dt>Protected infra</dt>
        <dd>{inspection.features.protectedBikeInfrastructure ? "yes" : "no"}</dd>
      </dl>
      {(inspection.bikeability.reasons ?? []).length > 0 && (
        <ul className="inspection-reasons">
          {(inspection.bikeability.reasons ?? []).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
