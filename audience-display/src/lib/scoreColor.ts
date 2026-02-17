/** Map a 0-10 score to a Tailwind-compatible color string. */
export function scoreColor(score: number): string {
  if (score < 4) return "#ff4444";
  if (score < 6) return "#ff8c00";
  if (score < 8) return "#00ff88";
  return "#ffd700";
}
