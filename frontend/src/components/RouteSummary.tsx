import type { RouteResponse } from "../types/api";
import { formatDistance, formatElevation, type UnitSystem } from "../units";

type Props = {
  route: RouteResponse | null;
  unitSystem: UnitSystem;
};

export function RouteSummary({ route, unitSystem }: Props) {
  if (!route) {
    return <p className="summary placeholder">No route yet.</p>;
  }

  return (
    <dl className="summary">
      <div>
        <dt>Distance</dt>
        <dd>{formatDistance(route.distanceM, unitSystem)}</dd>
      </div>
      <div>
        <dt>Bikeability</dt>
        <dd>{route.averageBikeability.toFixed(1)} / 10</dd>
      </div>
      <div>
        <dt>Elevation</dt>
        <dd>+{formatElevation(route.elevationGainM, unitSystem)}</dd>
      </div>
      <div>
        <dt>High quality</dt>
        <dd>{Math.round(route.pctHighQuality * 100)}%</dd>
      </div>
    </dl>
  );
}
