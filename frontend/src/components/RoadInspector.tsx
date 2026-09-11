import { X } from "lucide-react";
import type { RoadInspectionResponse } from "../types/api";

type Props = {
  inspection: RoadInspectionResponse | null;
  onClose: () => void;
};

export function RoadInspector({ inspection, onClose }: Props) {
  if (!inspection) {
    return null;
  }

  return (
    <section className="road-inspector" aria-live="polite">
      <button type="button" className="close-button" onClick={onClose} aria-label="Close">
        <X size={16} strokeWidth={1.75} />
      </button>
      <h2>Road</h2>
      <p className="score-line">
        Bikeability <strong>{inspection.bikeability.score.toFixed(1)}</strong> / 10
      </p>
      <dl>
        <dt>Highway</dt>
        <dd>{inspection.features.highway ?? "unknown"}</dd>
        <dt>Speed</dt>
        <dd>
          {inspection.features.speedKph
            ? `${Math.round(inspection.features.speedKph * 0.621371)} mph`
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
