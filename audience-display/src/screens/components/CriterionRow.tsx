import { motion } from "framer-motion";
import { scoreColor } from "../../lib/scoreColor";
import type { CriterionEntry } from "../../store/displayStore";

interface CriterionRowProps {
  criterion: CriterionEntry;
  index: number;
}

export function CriterionRow({ criterion, index }: CriterionRowProps) {
  const color = scoreColor(criterion.score);
  const pct = (criterion.score / 10) * 100;

  return (
    <motion.div
      initial={{ opacity: 0, x: -40 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.5, duration: 0.6, ease: "easeOut" }}
      className="flex flex-col gap-2"
    >
      <div className="flex items-baseline justify-between">
        <span className="text-2xl text-arbiter-text font-medium">
          {criterion.name}
          <span className="text-arbiter-muted text-lg ml-3">
            (×{criterion.weight.toFixed(1)})
          </span>
        </span>
        <span className="text-3xl font-bold" style={{ color }}>
          {criterion.score.toFixed(1)}
        </span>
      </div>

      <div className="h-4 rounded-full bg-arbiter-surface overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ delay: index * 0.5 + 0.2, duration: 0.7, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ background: `linear-gradient(90deg, ${color}88, ${color})` }}
        />
      </div>

      {criterion.justification && (
        <p className="text-lg text-arbiter-muted leading-snug mt-1">
          {criterion.justification}
        </p>
      )}
    </motion.div>
  );
}
