import { motion } from "framer-motion";
import { scoreColor } from "../../lib/scoreColor";
import { formatScore } from "../../lib/formatScore";

interface ScoreTotalProps {
  totalScore: number;
  track: string;
}

export function ScoreTotal({ totalScore, track }: ScoreTotalProps) {
  const color = scoreColor(totalScore);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className="flex flex-col items-center gap-2 mt-6"
    >
      <span className="text-sm text-arbiter-muted uppercase tracking-widest">
        Total Score
      </span>
      <span
        className="text-6xl font-bold animate-score-pulse"
        style={{ color }}
      >
        {formatScore(totalScore)}
      </span>
      {track && (
        <span className="text-sm text-arbiter-accent tracking-wide">
          Track: {track}
        </span>
      )}
    </motion.div>
  );
}
