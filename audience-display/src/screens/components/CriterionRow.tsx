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
      transition={{ delay: index * 0.1, duration: 0.5, ease: "easeOut" }}
      className="flex flex-col gap-1.5"
    >
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-arbiter-text font-medium">
          {criterion.name}
          <span className="text-arbiter-muted text-xs ml-2">
            (×{criterion.weight.toFixed(1)})
          </span>
        </span>
        <span className="text-lg font-bold" style={{ color }}>
          {criterion.score.toFixed(1)}
        </span>
      </div>

      <div className="h-2 rounded-full bg-arbiter-surface overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ delay: index * 0.1 + 0.2, duration: 0.6, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ background: `linear-gradient(90deg, ${color}88, ${color})` }}
        />
      </div>

      {criterion.justification && (
        <p className="text-xs text-arbiter-muted leading-snug mt-0.5">
          {criterion.justification}
        </p>
      )}
    </motion.div>
  );
}
