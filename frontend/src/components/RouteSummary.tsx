import { LoaderCircle } from "lucide-react";
import type { RouteResponse } from "../types/api";

type Props = {
  route: RouteResponse | null;
  loading: boolean;
};

export function RouteSummary({ route, loading }: Props) {
  if (loading) {
    return (
      <p className="summary placeholder summary-loading" role="status" aria-live="polite">
        <LoaderCircle className="spin" size={16} strokeWidth={2} aria-hidden />
        Computing route…
      </p>
    );
  }
  if (!route) {
    return <p className="summary placeholder">No route yet.</p>;
  }

  return (
    <dl className="summary">
      <div>
        <dt>Distance</dt>
        <dd>{(route.distanceM / 1609.34).toFixed(1)} mi</dd>
      </div>
      <div>
        <dt>Bikeability</dt>
        <dd>{route.averageBikeability.toFixed(1)} / 10</dd>
      </div>
      <div>
        <dt>Elevation</dt>
        <dd>+{Math.round(route.elevationGainM * 3.28084)} ft</dd>
      </div>
      <div>
        <dt>High quality</dt>
        <dd>{Math.round(route.pctHighQuality * 100)}%</dd>
      </div>
    </dl>
  );
}
