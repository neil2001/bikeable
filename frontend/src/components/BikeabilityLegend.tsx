import { bikeabilityLegendGradient } from "../map/colors";

type Props = {
  showHeatmap: boolean;
  onToggleHeatmap: () => void;
  bikeabilityMin: number;
  bikeabilityMax: number;
  onBikeabilityMinChange: (min: number) => void;
  onBikeabilityMaxChange: (max: number) => void;
};

export function BikeabilityLegend({
  showHeatmap,
  onToggleHeatmap,
  bikeabilityMin,
  bikeabilityMax,
  onBikeabilityMinChange,
  onBikeabilityMaxChange,
}: Props) {
  const minPct = (bikeabilityMin / 10) * 100;
  const maxPct = (bikeabilityMax / 10) * 100;
  const minOnTop = bikeabilityMin > 10 - bikeabilityMax;

  const handleMinChange = (value: number) => {
    onBikeabilityMinChange(Math.min(value, bikeabilityMax));
  };

  const handleMaxChange = (value: number) => {
    onBikeabilityMaxChange(Math.max(value, bikeabilityMin));
  };

  return (
    <div className="legend" aria-label="Bikeability legend">
      <div className="legend-header">
        <label className="legend-toggle">
          <input
            type="checkbox"
            checked={showHeatmap}
            onChange={onToggleHeatmap}
          />
          <strong>Bikeability</strong>
        </label>
        {showHeatmap && (
          <span className="legend-range-val">
            {bikeabilityMin.toFixed(1)}–{bikeabilityMax.toFixed(1)}
          </span>
        )}
      </div>

      {showHeatmap && (
        <>
          <div className="legend-range-track">
            <div
              className="legend-bar"
              style={{ background: bikeabilityLegendGradient() }}
            />
            <div
              className="legend-range-mask legend-range-mask-left"
              style={{ width: `${minPct}%` }}
            />
            <div
              className="legend-range-mask legend-range-mask-right"
              style={{ width: `${100 - maxPct}%` }}
            />
            <input
              type="range"
              className="legend-range-input"
              style={{ zIndex: minOnTop ? 4 : 3 }}
              min={0}
              max={10}
              step={0.5}
              value={bikeabilityMin}
              onChange={(e) => handleMinChange(Number(e.target.value))}
              aria-label="Minimum bikeability"
            />
            <input
              type="range"
              className="legend-range-input"
              style={{ zIndex: minOnTop ? 3 : 4 }}
              min={0}
              max={10}
              step={0.5}
              value={bikeabilityMax}
              onChange={(e) => handleMaxChange(Number(e.target.value))}
              aria-label="Maximum bikeability"
            />
          </div>
          <div className="legend-scale">
            <span>0 Poor</span>
            <span>5 Moderate</span>
            <span>10 Excellent</span>
          </div>
        </>
      )}
    </div>
  );
}
