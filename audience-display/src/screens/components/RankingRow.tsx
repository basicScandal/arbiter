import { motion } from "framer-motion";
import { scoreColor } from "../../lib/scoreColor";
import type { RankingEntry } from "../../store/displayStore";

interface RankingRowProps {
  entry: RankingEntry;
  index: number;
  isWinner?: boolean;
}

export function RankingRow({ entry, index, isWinner }: RankingRowProps) {
  const color = scoreColor(entry.totalScore);

  return (
    <motion.tr
      initial={{ opacity: 0, x: -30 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.6, duration: 0.5, ease: "easeOut" }}
      className={`border-b ${isWinner ? "border-yellow-400/40" : "border-arbiter-accent/10"}`}
    >
      <td
        className={`py-4 pr-4 text-center w-20 font-black ${
          isWinner
            ? "text-4xl text-yellow-400 drop-shadow-[0_0_12px_rgba(250,204,21,0.7)]"
            : "text-3xl text-arbiter-accent"
        }`}
      >
        #{entry.rank}
      </td>
      <td
        className={`py-4 pr-4 font-medium ${
          isWinner
            ? "text-3xl text-yellow-100 drop-shadow-[0_0_8px_rgba(250,204,21,0.4)]"
            : "text-2xl text-arbiter-text"
        }`}
      >
        {entry.teamName}
        {isWinner && (
          <motion.span
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.4, type: "spring" }}
            className="ml-3 text-yellow-400 text-2xl"
          >
            WINNER
          </motion.span>
        )}
      </td>
      <td
        className={`py-4 pr-4 font-bold text-center ${isWinner ? "text-3xl" : "text-2xl"}`}
        style={{
          color,
          filter: isWinner ? "drop-shadow(0 0 8px rgba(250,204,21,0.5))" : undefined,
        }}
      >
        {entry.totalScore.toFixed(1)}
      </td>
      <td className={`py-4 pr-4 text-arbiter-muted ${isWinner ? "text-xl" : "text-lg"}`}>
        {entry.track}
      </td>
      <td className="py-4 text-lg text-arbiter-muted max-w-md">
        {entry.reasoning}
      </td>
    </motion.tr>
  );
}
