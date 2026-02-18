import { motion } from "framer-motion";
import { useOperatorStore } from "../store/operatorStore";

function getEasterEgg(attacks: number, clean: number, demoState: string, startedAt: number | null): string | null {
  const total = attacks + clean;
  const shieldPercent = total > 0 ? (clean / total) * 100 : 100;

  // Injection streak taunt
  if (attacks >= 5 && shieldPercent >= 80) return "Is that all you've got?";

  // Perfect shield at end of demo
  if (demoState === "stopped" && total > 0 && shieldPercent === 100) return "Flawless defense.";

  // Speed run detection
  if (demoState === "stopped" && startedAt) {
    const duration = Date.now() / 1000 - startedAt;
    if (duration < 30 && duration > 0) return "That was... brief.";
  }

  return null;
}

export function DefenseStrip() {
  const counters = useOperatorStore((s) => s.counters);
  const events = useOperatorStore((s) => s.events);
  const demoState = useOperatorStore((s) => s.demoState);
  const startedAt = useOperatorStore((s) => s.startedAt);

  const lastRoast = events.find((e) => e.event_type === "roast_generated");
  const roastText = lastRoast?.data?.text ? String(lastRoast.data.text) : "";
  const easterEgg = getEasterEgg(counters.attacks, counters.clean, demoState, startedAt);

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
      {roastText ? (
        <div className="flex-1 text-event-roast text-sm truncate italic ml-2">
          &ldquo;{roastText}&rdquo;
        </div>
      ) : easterEgg ? (
        <motion.div
          key={easterEgg}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex-1 text-accent-capturing text-sm truncate italic ml-2"
          style={{ textShadow: "0 0 8px rgba(0, 255, 136, 0.3)" }}
        >
          {easterEgg}
        </motion.div>
      ) : null}
    </div>
  );
}
