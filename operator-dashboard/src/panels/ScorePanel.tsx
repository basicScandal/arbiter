import { motion, AnimatePresence } from "framer-motion";
import { useOperatorStore } from "../store/operatorStore";

const PHASE_CONFIG = {
  sanitizing: { label: "SANITIZING OBSERVATIONS", step: 1 },
  scoring: { label: "SCORING DEMO", step: 2 },
  revealing: { label: "FINALIZING VERDICT", step: 3 },
} as const;

function JudgmentProgress({ phase }: { phase: 'sanitizing' | 'scoring' | 'revealing' }) {
  const config = PHASE_CONFIG[phase];
  return (
    <motion.div
      key={phase}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.3 }}
      className="text-center py-8 space-y-3"
    >
      <div className="text-sm font-bold tracking-wider" style={{ color: 'var(--accent)' }}>
        <span>{config.label}</span>
        <motion.span
          animate={{ opacity: [1, 0.2, 1] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
        >
          ...
        </motion.span>
      </div>
      <div className="flex justify-center items-center gap-1.5">
        {[1, 2, 3].map((s) => (
          <div
            key={s}
            className="w-1.5 h-1.5 rounded-full transition-colors duration-300"
            style={{
              backgroundColor: s <= config.step
                ? 'var(--accent)'
                : 'rgba(var(--accent-rgb), 0.2)',
            }}
          />
        ))}
        <span className="text-text-dim text-xs ml-1.5">{config.step}/3</span>
      </div>
    </motion.div>
  );
}

export function ScorePanel() {
  const lastScorecard = useOperatorStore((s) => s.lastScorecard);
  const scoringPhase = useOperatorStore((s) => s.scoringPhase);

  const showJudgment = !lastScorecard && scoringPhase && scoringPhase !== 'idle'
    && (scoringPhase === 'sanitizing' || scoringPhase === 'scoring' || scoringPhase === 'revealing');

  return (
    <div className="glass-panel p-4 animate-border-glow">
      <h2 className="section-label mb-3">SCORE</h2>
      <AnimatePresence mode="wait">
        {lastScorecard ? (
          <motion.div
            key={`score-${lastScorecard.team_name}`}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, ease: "easeOut" as const }}
            className="space-y-3"
          >
            {/* Team + Track header */}
            <div className="flex justify-between items-baseline">
              <span className="text-text-primary text-sm font-bold truncate mr-2">
                {lastScorecard.team_name}
              </span>
              <span className="text-text-dim text-xs shrink-0">
                {lastScorecard.track}
              </span>
            </div>

            {/* Total score - prominent with animated reveal */}
            <motion.div
              className="text-center py-2"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.2, duration: 0.5, ease: "easeOut" as const }}
            >
              <span className="text-3xl font-bold text-accent-capturing">
                {lastScorecard.total_score.toFixed(1)}
              </span>
              <span className="text-text-dim text-xs ml-1">/10</span>
            </motion.div>

            {/* Per-criterion breakdown */}
            <div className="space-y-1">
              {lastScorecard.criteria.map((c, i) => (
                <motion.div
                  key={c.name}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 + i * 0.06, duration: 0.25 }}
                  className="flex justify-between items-center text-xs"
                >
                  <span className="text-text-dim truncate mr-2" title={c.justification}>
                    {c.name}
                  </span>
                  <div className="flex items-center gap-1 shrink-0">
                    <span className="text-text-dim">{"\u00D7"}{c.weight}</span>
                    <span className="text-text-primary font-bold w-8 text-right">
                      {c.score.toFixed(1)}
                    </span>
                  </div>
                </motion.div>
              ))}

              {/* Track bonus if present */}
              {lastScorecard.track_bonus && (
                <motion.div
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 + lastScorecard.criteria.length * 0.06, duration: 0.25 }}
                  className="flex justify-between items-center text-xs border-t border-text-dim/20 pt-1 mt-1"
                >
                  <span className="text-accent-capturing truncate mr-2" title={lastScorecard.track_bonus.justification}>
                    {lastScorecard.track_bonus.name}
                  </span>
                  <div className="flex items-center gap-1 shrink-0">
                    <span className="text-text-dim">{"\u00D7"}{lastScorecard.track_bonus.weight}</span>
                    <span className="text-accent-capturing font-bold w-8 text-right">
                      {lastScorecard.track_bonus.score.toFixed(1)}
                    </span>
                  </div>
                </motion.div>
              )}
            </div>
          </motion.div>
        ) : showJudgment ? (
          <JudgmentProgress phase={scoringPhase as 'sanitizing' | 'scoring' | 'revealing'} />
        ) : (
          <motion.div
            key="awaiting"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="text-text-dim text-center py-8 text-sm"
          >
            Awaiting judgment...
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
