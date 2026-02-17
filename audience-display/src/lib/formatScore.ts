/** Format a numeric score as "X.Y / 10". */
export function formatScore(score: number): string {
  return `${score.toFixed(1)} / 10`;
}
