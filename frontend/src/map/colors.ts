/** Cycling-lane green — keep in sync with `--accent` in index.css. */
export const ACCENT = "#2f6b4f";

/** Navigation blue — keep in sync with `--route` in index.css. */
export const ROUTE_COLOR = "#2563eb";
export const ROUTE_CASING = "#ffffff";

/** Thirds of the 0–10 bikeability scale. */
export const BIKEABILITY_POOR_MAX = 10 / 3; // ~3.3
export const BIKEABILITY_GOOD_MIN = (10 / 3) * 2; // ~6.6
export const BIKEABILITY_MID = 5; // center of scale / middle of yellow band

const BLEND = 0.3; // narrow transition band at each third boundary

/**
 * Sequential bikeability stops shared by map layer and legend:
 * - 0–3.3: Poor (muted neutral grey)
 * - 3.3–6.6: Moderate (warm amber/yellow)
 * - 6.6–10: Good to Excellent (green transitioning into teal)
 *
 * Smooth linear transitions blend across each boundary.
 */
export const BIKEABILITY_STOPS: { score: number; color: string }[] = [
  { score: 0, color: "#94a3b8" },
  { score: BIKEABILITY_POOR_MAX - BLEND, color: "#94a3b8" },
  { score: BIKEABILITY_POOR_MAX + BLEND, color: "#eab308" },
  { score: BIKEABILITY_GOOD_MIN - BLEND, color: "#eab308" },
  { score: BIKEABILITY_GOOD_MIN + BLEND, color: "#16a34a" },
  { score: 10, color: "#0d9488" },
];

export function bikeabilityColor(score: number): string {
  if (score <= BIKEABILITY_STOPS[0].score) return BIKEABILITY_STOPS[0].color;
  for (let i = 1; i < BIKEABILITY_STOPS.length; i++) {
    const prev = BIKEABILITY_STOPS[i - 1];
    const curr = BIKEABILITY_STOPS[i];
    if (score <= curr.score) {
      const t = (score - prev.score) / (curr.score - prev.score);
      return lerpColor(prev.color, curr.color, t);
    }
  }
  return BIKEABILITY_STOPS[BIKEABILITY_STOPS.length - 1].color;
}

export function bikeabilityLegendGradient(): string {
  const stops = BIKEABILITY_STOPS.map(({ score, color }) => {
    const pct = (score / 10) * 100;
    return `${color} ${pct}%`;
  });
  return `linear-gradient(to right, ${stops.join(", ")})`;
}

function lerpColor(from: string, to: string, t: number): string {
  const parse = (hex: string) => {
    const n = Number.parseInt(hex.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255] as const;
  };
  const [r1, g1, b1] = parse(from);
  const [r2, g2, b2] = parse(to);
  const r = Math.round(r1 + (r2 - r1) * t);
  const g = Math.round(g1 + (g2 - g1) * t);
  const b = Math.round(b1 + (b2 - b1) * t);
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}
