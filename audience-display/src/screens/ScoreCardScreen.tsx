import { motion } from "framer-motion";
import { useDisplayStore } from "../store/displayStore";
import { CriterionRow } from "./components/CriterionRow";
import { ScoreTotal } from "./components/ScoreTotal";

export function ScoreCardScreen() {
  const teamName = useDisplayStore((s) => s.scoreTeamName);
  const criteria = useDisplayStore((s) => s.criteria);
  const scoreTotal = useDisplayStore((s) => s.scoreTotal);

  return (
    <div className="flex flex-col items-center h-full px-16 py-10 gap-8">
      <motion.h2
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-3xl text-arbiter-accent tracking-widest uppercase shrink-0"
      >
        Score Reveal — {teamName}
      </motion.h2>

      <div className="w-full max-w-4xl flex flex-col gap-7 overflow-y-auto min-h-0 flex-1">
        {criteria.map((c, i) => (
          <CriterionRow key={c.name} criterion={c} index={i} />
        ))}
      </div>

      {scoreTotal && (
        <div className="shrink-0">
          <ScoreTotal
            totalScore={scoreTotal.totalScore}
            track={scoreTotal.track}
          />
        </div>
      )}
    </div>
  );
}
