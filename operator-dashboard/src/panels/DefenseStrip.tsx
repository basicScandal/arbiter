import { motion } from "framer-motion";
import { useOperatorStore } from "../store/operatorStore";

export function DefenseStrip() {
  const counters = useOperatorStore((s) => s.counters);
  const events = useOperatorStore((s) => s.events);

  const lastRoast = events.find((e) => e.event_type === "roast_generated");
  const roastText = lastRoast?.data?.text ? String(lastRoast.data.text) : "";

  return (
    <div className="glass-panel px-4 py-2 flex items-center gap-4 animate-border-glow">
      <span className="text-xs tracking-widest text-text-dim uppercase shrink-0">
        DEFENSE
      </span>
      <motion.span
        key={`atk-${counters.attacks}`}
        className="text-event-injection font-mono font-bold tabular-nums"
        initial={{ scale: 1.3 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.2 }}
      >
        {counters.attacks}
      </motion.span>
      <span className="text-text-dim text-xs">blocked</span>
      <motion.span
        key={`cln-${counters.clean}`}
        className="text-event-verified font-mono font-bold tabular-nums"
        initial={{ scale: 1.3 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.2 }}
      >
        {counters.clean}
      </motion.span>
      <span className="text-text-dim text-xs">clean</span>
      {roastText && (
        <div className="flex-1 text-event-roast text-sm truncate italic ml-2">
          &ldquo;{roastText}&rdquo;
        </div>
      )}
    </div>
  );
}
