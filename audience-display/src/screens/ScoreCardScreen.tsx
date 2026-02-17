import { motion } from "framer-motion";
import { useDisplayStore } from "../store/displayStore";
import { CriterionRow } from "./components/CriterionRow";
import { ScoreTotal } from "./components/ScoreTotal";

export function ScoreCardScreen() {
  const teamName = useDisplayStore((s) => s.scoreTeamName);
  const criteria = useDisplayStore((s) => s.criteria);
  const scoreTotal = useDisplayStore((s) => s.scoreTotal);

  return (
    <div className="flex flex-col items-center h-full px-12 py-8 gap-6 overflow-auto">
      <motion.h2
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-xl text-arbiter-accent tracking-widest uppercase"
      >
        Score Reveal — {teamName}
      </motion.h2>

      <div className="w-full max-w-2xl flex flex-col gap-5">
        {criteria.map((c, i) => (
          <CriterionRow key={c.name} criterion={c} index={i} />
        ))}
      </div>

      {scoreTotal && (
        <ScoreTotal
          totalScore={scoreTotal.totalScore}
          track={scoreTotal.track}
        />
      )}
    </div>
  );
}
