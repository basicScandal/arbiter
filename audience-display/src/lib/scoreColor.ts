/** Map a 0-10 score to a Tailwind-compatible color string. */
export function scoreColor(score: number): string {
  const clamped = Math.max(0, Math.min(10, score));
  if (clamped < 4) return "#ff4444";   // red — poor
  if (clamped < 6) return "#ff8c00";   // orange — fair
  if (clamped < 8) return "#ffd700";   // gold — good
  return "#00ff88";                     // green — excellent
}
