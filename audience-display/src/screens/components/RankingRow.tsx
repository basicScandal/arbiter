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
      transition={{ delay: index * 0.6, duration: 0.5, ease: "easeOut" }}
      className="border-b border-arbiter-accent/10"
    >
      <td className="py-4 pr-4 text-3xl font-bold text-arbiter-accent text-center w-20">
        #{entry.rank}
      </td>
      <td className="py-4 pr-4 text-2xl text-arbiter-text font-medium">
        {entry.teamName}
      </td>
      <td className="py-4 pr-4 text-2xl font-bold text-center" style={{ color }}>
        {entry.totalScore.toFixed(1)}
      </td>
      <td className="py-4 pr-4 text-lg text-arbiter-muted">
        {entry.track}
      </td>
      <td className="py-4 text-base text-arbiter-muted max-w-md">
        {entry.reasoning}
      </td>
    </motion.tr>
  );
}
