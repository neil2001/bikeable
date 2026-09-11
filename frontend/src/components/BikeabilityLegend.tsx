type Props = {
  showHeatmap: boolean;
  onToggleHeatmap: () => void;
  opacity: number;
  onOpacityChange: (opacity: number) => void;
};

export function BikeabilityLegend({
  showHeatmap,
  onToggleHeatmap,
  opacity,
  onOpacityChange,
}: Props) {
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
          <span className="legend-opacity-val">{Math.round(opacity * 100)}%</span>
        )}
      </div>

      {showHeatmap && (
        <>
          <div className="legend-bar" />
          <div className="legend-scale">
            <span>0 Poor</span>
            <span>5 Moderate</span>
            <span>10 Excellent</span>
          </div>
          <div className="legend-opacity-slider">
            <span>Opacity</span>
            <input
              type="range"
              min={0.2}
              max={1.0}
              step={0.05}
              value={opacity}
              onChange={(e) => onOpacityChange(Number(e.target.value))}
              aria-label="Heatmap opacity"
            />
          </div>
        </>
      )}
    </div>
  );
}
