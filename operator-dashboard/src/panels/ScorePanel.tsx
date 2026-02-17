import { useOperatorStore } from "../store/operatorStore";

export function ScorePanel() {
  const lastScorecard = useOperatorStore((s) => s.lastScorecard);

  return (
    <div className="glass-panel p-4 animate-border-glow">
      <h2 className="section-label mb-3">SCORE</h2>
      {!lastScorecard ? (
        <div className="text-text-dim text-center py-8 text-sm">
          Awaiting judgment...
        </div>
      ) : (
        <div className="space-y-3">
          {/* Team + Track header */}
          <div className="flex justify-between items-baseline">
            <span className="text-text-bright text-sm font-bold truncate mr-2">
              {lastScorecard.team_name}
            </span>
            <span className="text-text-dim text-xs shrink-0">
              {lastScorecard.track}
            </span>
          </div>

          {/* Total score - prominent */}
          <div className="text-center py-2">
            <span className="text-3xl font-bold text-accent-capturing">
              {lastScorecard.total_score.toFixed(1)}
            </span>
            <span className="text-text-dim text-xs ml-1">/10</span>
          </div>

          {/* Per-criterion breakdown */}
          <div className="space-y-1">
            {lastScorecard.criteria.map((c) => (
              <div key={c.name} className="flex justify-between items-center text-xs">
                <span className="text-text-dim truncate mr-2" title={c.justification}>
                  {c.name}
                </span>
                <div className="flex items-center gap-1 shrink-0">
                  <span className="text-text-dim">{"\u00D7"}{c.weight}</span>
                  <span className="text-text-bright font-bold w-8 text-right">
                    {c.score.toFixed(1)}
                  </span>
                </div>
              </div>
            ))}

            {/* Track bonus if present */}
            {lastScorecard.track_bonus && (
              <div className="flex justify-between items-center text-xs border-t border-text-dim/20 pt-1 mt-1">
                <span className="text-accent-capturing truncate mr-2" title={lastScorecard.track_bonus.justification}>
                  {lastScorecard.track_bonus.name}
                </span>
                <div className="flex items-center gap-1 shrink-0">
                  <span className="text-text-dim">{"\u00D7"}{lastScorecard.track_bonus.weight}</span>
                  <span className="text-accent-capturing font-bold w-8 text-right">
                    {lastScorecard.track_bonus.score.toFixed(1)}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
