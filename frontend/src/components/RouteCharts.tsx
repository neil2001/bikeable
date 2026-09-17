import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RouteResponse } from "../types/api";
import { formatDistance, formatElevation, type UnitSystem } from "../units";

type Props = {
  route: RouteResponse | null;
  cursorDistanceM: number | null;
  onCursorChange: (distanceM: number | null) => void;
  unitSystem: UnitSystem;
};

type ChartPoint = {
  distanceM: number;
  elevation: number | null;
  bikeability: number;
};

export function RouteCharts({ route, cursorDistanceM, onCursorChange, unitSystem }: Props) {
  if (!route || route.profile.length === 0) {
    return null;
  }

  const hasElevation = route.profile.some((sample) => sample.elevationM != null);
  const chartData: ChartPoint[] = route.profile.map((sample) => ({
    distanceM: sample.distanceM,
    elevation: sample.elevationM,
    bikeability: sample.bikeability,
  }));

  const formatDistanceTick = (distanceM: number) => formatDistance(distanceM, unitSystem);
  const formatElevationTick = (elevationM: number) => formatElevation(elevationM, unitSystem);

  const handleCursor = (state: { activeTooltipIndex?: unknown }) => {
    const index = state?.activeTooltipIndex;
    if (typeof index !== "number") {
      onCursorChange(null);
      return;
    }
    onCursorChange(chartData[index]?.distanceM ?? null);
  };

  return (
    <div className="charts">
      <section aria-label="Elevation profile">
        <h3>Elevation</h3>
        <p className="chart-summary">
          {hasElevation
            ? `Elevation gain: ${formatElevation(route.elevationGainM, unitSystem)}.`
            : "Elevation data is unavailable for this route."}
        </p>
        {hasElevation ? (
          <ResponsiveContainer width="100%" height={140}>
            <LineChart
              data={chartData}
              onMouseMove={(state) => handleCursor(state)}
              onMouseLeave={() => onCursorChange(null)}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="distanceM" tickFormatter={formatDistanceTick} />
              <YAxis tickFormatter={(value) => formatElevationTick(Number(value))} />
              <Tooltip
                labelFormatter={(value) => formatDistanceTick(Number(value))}
                formatter={(value) => [formatElevationTick(Number(value)), "Elevation"]}
              />
              <Line
                type="monotone"
                dataKey="elevation"
                stroke="#2563eb"
                dot={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        ) : null}
      </section>
      <section aria-label="Bikeability profile">
        <h3>Bikeability</h3>
        <p className="chart-summary">
          Average bikeability: {route.averageBikeability.toFixed(1)} / 10.
        </p>
        <ResponsiveContainer width="100%" height={140}>
          <LineChart
            data={chartData}
            onMouseMove={(state) => handleCursor(state)}
            onMouseLeave={() => onCursorChange(null)}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="distanceM" tickFormatter={formatDistanceTick} />
            <YAxis domain={[0, 10]} />
            <Tooltip
              labelFormatter={(value) => formatDistanceTick(Number(value))}
              formatter={(value) => [Number(value).toFixed(2), "Bikeability"]}
            />
            <Line type="monotone" dataKey="bikeability" stroke="#059669" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </section>
      {cursorDistanceM !== null ? (
        <p className="chart-summary">
          Selected distance: {formatDistance(cursorDistanceM, unitSystem)}
        </p>
      ) : null}
    </div>
  );
}
