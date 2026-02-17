import { motion } from "framer-motion";
import { useDisplayStore } from "../store/displayStore";
import { CriterionRow } from "./components/CriterionRow";
import { ScoreTotal } from "./components/ScoreTotal";

export function ScoreCardScreen() {
  const teamName = useDisplayStore((s) => s.scoreTeamName);
  const criteria = useDisplayStore((s) => s.criteria);
  const scoreTotal = useDisplayStore((s) => s.scoreTotal);

  return (
    <div className="flex flex-col items-center h-full px-16 py-10 gap-8 overflow-auto">
      <motion.h2
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-3xl text-arbiter-accent tracking-widest uppercase"
      >
        Score Reveal — {teamName}
      </motion.h2>

      <div className="w-full max-w-4xl flex flex-col gap-7">
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
