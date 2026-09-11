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

const METERS_TO_FEET = 3.28084;

type Props = {
  route: RouteResponse | null;
  cursorDistanceM: number | null;
  onCursorChange: (distanceM: number | null) => void;
};

type ChartPoint = {
  distanceM: number;
  elevationFt: number | null;
  bikeability: number;
};

function formatMiles(distanceM: number): string {
  return `${(distanceM / 1609.34).toFixed(1)} mi`;
}

function formatFeet(value: number): string {
  return `${Math.round(value)} ft`;
}

export function RouteCharts({ route, cursorDistanceM, onCursorChange }: Props) {
  if (!route || route.profile.length === 0) {
    return null;
  }

  const hasElevation = route.profile.some((sample) => sample.elevationM != null);
  const chartData: ChartPoint[] = route.profile.map((sample) => ({
    distanceM: sample.distanceM,
    elevationFt:
      sample.elevationM == null ? null : sample.elevationM * METERS_TO_FEET,
    bikeability: sample.bikeability,
  }));

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
            ? `Elevation gain: ${Math.round(route.elevationGainM * METERS_TO_FEET)} ft.`
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
              <XAxis dataKey="distanceM" tickFormatter={formatMiles} />
              <YAxis tickFormatter={(value) => `${Math.round(Number(value))}`} />
              <Tooltip
                labelFormatter={(value) => formatMiles(Number(value))}
                formatter={(value) => [formatFeet(Number(value)), "Elevation"]}
              />
              <Line
                type="monotone"
                dataKey="elevationFt"
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
            <XAxis dataKey="distanceM" tickFormatter={formatMiles} />
            <YAxis domain={[0, 10]} />
            <Tooltip
              labelFormatter={(value) => formatMiles(Number(value))}
              formatter={(value) => [Number(value).toFixed(2), "Bikeability"]}
            />
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
