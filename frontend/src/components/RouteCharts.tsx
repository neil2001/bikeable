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

type Props = {
  route: RouteResponse | null;
  cursorDistanceM: number | null;
  onCursorChange: (distanceM: number | null) => void;
};

function formatMiles(distanceM: number): string {
  return `${(distanceM / 1609.34).toFixed(1)} mi`;
}

export function RouteCharts({ route, cursorDistanceM, onCursorChange }: Props) {
  if (!route || route.profile.length === 0) {
    return null;
  }

  const chartData = route.profile.map((sample) => ({
    distanceM: sample.distanceM,
    elevationM: sample.elevationM ?? 0,
    bikeability: sample.bikeability,
  }));

  return (
    <div className="charts">
      <section aria-label="Elevation profile">
        <h3>Elevation</h3>
        <p className="chart-summary">
          Elevation gain: {Math.round(route.elevationGainM * 3.28084)} ft.
        </p>
        <ResponsiveContainer width="100%" height={140}>
          <LineChart
            data={chartData}
            onMouseMove={(state) => {
              const index = state?.activeTooltipIndex;
              if (typeof index !== "number") {
                onCursorChange(null);
                return;
              }
              onCursorChange(chartData[index]?.distanceM ?? null);
            }}
            onMouseLeave={() => onCursorChange(null)}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="distanceM" tickFormatter={formatMiles} />
            <YAxis />
            <Tooltip labelFormatter={(value) => formatMiles(Number(value))} />
            <Line type="monotone" dataKey="elevationM" stroke="#2563eb" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </section>
      <section aria-label="Bikeability profile">
        <h3>Bikeability</h3>
        <p className="chart-summary">
          Average bikeability: {route.averageBikeability.toFixed(1)} / 10.
        </p>
        <ResponsiveContainer width="100%" height={140}>
          <LineChart
            data={chartData}
            onMouseMove={(state) => {
              const index = state?.activeTooltipIndex;
              if (typeof index !== "number") {
                onCursorChange(null);
                return;
              }
              onCursorChange(chartData[index]?.distanceM ?? null);
            }}
            onMouseLeave={() => onCursorChange(null)}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="distanceM" tickFormatter={formatMiles} />
            <YAxis domain={[0, 10]} />
            <Tooltip labelFormatter={(value) => formatMiles(Number(value))} />
            <Line type="monotone" dataKey="bikeability" stroke="#059669" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </section>
      {cursorDistanceM !== null ? (
        <p className="chart-summary">Selected distance: {formatMiles(cursorDistanceM)}</p>
      ) : null}
    </div>
  );
}
