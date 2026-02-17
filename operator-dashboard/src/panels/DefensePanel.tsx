import { motion } from "framer-motion";
import { useOperatorStore } from "../store/operatorStore";

export function DefensePanel() {
  const counters = useOperatorStore((s) => s.counters);

  const total = counters.attacks + counters.clean;
  const shieldPercent = total > 0 ? Math.round((counters.clean / total) * 100) : 100;

  const shieldColor =
    shieldPercent >= 80 ? "#00ff88" :
    shieldPercent >= 50 ? "#ffaa00" : "#ff4444";

  return (
    <div className="glass-panel p-4 animate-border-glow">
      <h2 className="section-label mb-3">DEFENSE MATRIX</h2>
      <div className="space-y-3">
        <div className="flex justify-between items-baseline">
          <span className="text-text-dim text-xs">Blocked</span>
          <motion.span
            key={`atk-${counters.attacks}`}
            className="text-event-injection font-bold text-lg tabular-nums"
            initial={{ scale: 1.4, color: "#ff4444" }}
            animate={{ scale: 1, color: "#ff4444" }}
            transition={{ duration: 0.3 }}
          >
            {counters.attacks}
          </motion.span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className="text-text-dim text-xs">Clean</span>
          <motion.span
            key={`cln-${counters.clean}`}
            className="text-event-verified font-bold text-lg tabular-nums"
            initial={{ scale: 1.4, color: "#00ff88" }}
            animate={{ scale: 1, color: "#00ff88" }}
            transition={{ duration: 0.3 }}
          >
            {counters.clean}
          </motion.span>
        </div>
        <div className="pt-2 border-t border-[var(--border-accent)]">
          <div className="flex justify-between items-baseline mb-2">
            <span className="text-text-dim text-xs">Shield</span>
            <motion.span
              key={shieldPercent}
              className="font-bold text-2xl tabular-nums"
              style={{ color: shieldColor, textShadow: `0 0 12px ${shieldColor}40` }}
              initial={{ scale: 1.2 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.3 }}
            >
              {shieldPercent}%
            </motion.span>
          </div>
          <div className="w-full bg-void rounded-full h-2 overflow-hidden">
            <motion.div
              className="h-full rounded-full"
              initial={false}
              animate={{ width: `${shieldPercent}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              style={{
                backgroundColor: shieldColor,
                boxShadow: `0 0 12px ${shieldColor}60`,
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
