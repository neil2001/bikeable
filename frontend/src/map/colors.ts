/** Cycling-lane green — keep in sync with `--accent` in index.css. */
export const ACCENT = "#2f6b4f";

/** Navigation blue — keep in sync with `--route` in index.css. */
export const ROUTE_COLOR = "#2563eb";
export const ROUTE_CASING = "#ffffff";

/** Sequential bikeability stops (0, 5, 8, 10) shared by map layer and legend. */
export const BIKEABILITY_STOPS: { score: number; color: string }[] = [
  { score: 0, color: "#c9c4b8" },
  { score: 5, color: "#7d9460" },
  { score: 8, color: "#2f6b4f" },
  { score: 10, color: "#1b9e77" },
];

export function bikeabilityColor(score: number): string {
  if (score >= 10) return BIKEABILITY_STOPS[3].color;
  if (score >= 8) {
    const t = (score - 8) / 2;
    return lerpColor(BIKEABILITY_STOPS[2].color, BIKEABILITY_STOPS[3].color, t);
  }
  if (score >= 5) {
    const t = (score - 5) / 3;
    return lerpColor(BIKEABILITY_STOPS[1].color, BIKEABILITY_STOPS[2].color, t);
  }
  const t = score / 5;
  return lerpColor(BIKEABILITY_STOPS[0].color, BIKEABILITY_STOPS[1].color, t);
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
