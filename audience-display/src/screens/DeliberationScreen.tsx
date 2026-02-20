import { motion } from "framer-motion";
import { useDisplayStore } from "../store/displayStore";
import { RankingRow } from "./components/RankingRow";
import { NarrativeBlock } from "./components/NarrativeBlock";

export function DeliberationScreen() {
  const rankings = useDisplayStore((s) => s.rankings);
  const narrative = useDisplayStore((s) => s.narrative);

  // Rankings arrive worst-first (highest rank number first, rank 1 last).
  // We display them in arrival order (no sorting).
  // The last entry to arrive with rank === 1 gets the winner treatment.
  const lastEntry = rankings[rankings.length - 1];
  const winnerId = lastEntry?.rank === 1 ? lastEntry.rank : null;

  return (
    <div className="flex flex-col items-center h-full px-16 py-10 gap-8 overflow-auto">
      <motion.h2
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-3xl text-arbiter-accent tracking-widest uppercase"
      >
        Final Deliberation
      </motion.h2>

      {rankings.length > 0 && (
        <table className="w-full max-w-5xl">
          <thead>
            <tr className="text-base text-arbiter-muted uppercase tracking-wider border-b border-arbiter-accent/20">
              <th className="pb-3 text-center w-20">Rank</th>
              <th className="pb-3 text-left">Team</th>
              <th className="pb-3 text-center">Score</th>
              <th className="pb-3 text-left">Track</th>
              <th className="pb-3 text-left">Reasoning</th>
            </tr>
          </thead>
          <tbody>
            {rankings.map((entry, i) => (
              <RankingRow
                key={`${entry.rank}-${entry.teamName}`}
                entry={entry}
                index={i}
                isWinner={winnerId !== null && entry.rank === 1}
              />
            ))}
          </tbody>
        </table>
      )}

      {narrative && <NarrativeBlock text={narrative} />}
    </div>
  );
}
