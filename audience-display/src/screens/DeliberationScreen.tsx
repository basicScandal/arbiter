import { motion } from "framer-motion";
import { useDisplayStore } from "../store/displayStore";
import { RankingRow } from "./components/RankingRow";
import { NarrativeBlock } from "./components/NarrativeBlock";

export function DeliberationScreen() {
  const rankings = useDisplayStore((s) => s.rankings);
  const narrative = useDisplayStore((s) => s.narrative);

  return (
    <div className="flex flex-col items-center h-full px-12 py-8 gap-6 overflow-auto">
      <motion.h2
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-xl text-arbiter-accent tracking-widest uppercase"
      >
        Final Deliberation
      </motion.h2>

      {rankings.length > 0 && (
        <table className="w-full max-w-4xl">
          <thead>
            <tr className="text-xs text-arbiter-muted uppercase tracking-wider border-b border-arbiter-accent/20">
              <th className="pb-2 text-center w-16">Rank</th>
              <th className="pb-2 text-left">Team</th>
              <th className="pb-2 text-center">Score</th>
              <th className="pb-2 text-left">Track</th>
              <th className="pb-2 text-left">Reasoning</th>
            </tr>
          </thead>
          <tbody>
            {rankings.map((entry, i) => (
              <RankingRow key={entry.rank} entry={entry} index={i} />
            ))}
          </tbody>
        </table>
      )}

      {narrative && <NarrativeBlock text={narrative} />}
    </div>
  );
}
