import { motion } from "framer-motion";
import { scoreColor } from "../../lib/scoreColor";
import type { RankingEntry } from "../../store/displayStore";

interface RankingRowProps {
  entry: RankingEntry;
  index: number;
}

export function RankingRow({ entry, index }: RankingRowProps) {
  const color = scoreColor(entry.totalScore);

  return (
    <motion.tr
      initial={{ opacity: 0, x: -30 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.15, duration: 0.5, ease: "easeOut" }}
      className="border-b border-arbiter-accent/10"
    >
      <td className="py-3 pr-4 text-2xl font-bold text-arbiter-accent text-center w-16">
        #{entry.rank}
      </td>
      <td className="py-3 pr-4 text-lg text-arbiter-text font-medium">
        {entry.teamName}
      </td>
      <td className="py-3 pr-4 text-lg font-bold text-center" style={{ color }}>
        {entry.totalScore.toFixed(1)}
      </td>
      <td className="py-3 pr-4 text-sm text-arbiter-muted">
        {entry.track}
      </td>
      <td className="py-3 text-xs text-arbiter-muted max-w-xs">
        {entry.reasoning}
      </td>
    </motion.tr>
  );
}
