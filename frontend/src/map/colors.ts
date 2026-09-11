/** Cycling-lane green — keep in sync with `--accent` in index.css. */
export const ACCENT = "#2f6b4f";

export function bikeabilityColor(score: number): string {
  if (score >= 8) return "#1b9e77";
  if (score >= 6) return "#66a61e";
  if (score >= 4) return "#d95f02";
  return "#e7298a";
}
