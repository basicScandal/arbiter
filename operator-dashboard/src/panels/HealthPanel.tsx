import { motion, AnimatePresence } from "framer-motion";
import { useOperatorStore } from "../store/operatorStore";

export function HealthPanel() {
  const health = useOperatorStore((s) => s.health);
  const entries = Object.entries(health);

  return (
    <div className="glass-panel p-4 animate-border-glow">
      <h2 className="section-label mb-3">SYSTEM HEALTH</h2>
      {entries.length === 0 ? (
        <div className="text-text-dim text-center py-2 text-xs">
          All systems nominal
        </div>
      ) : (
        <div className="space-y-1">
          <AnimatePresence initial={false}>
            {entries.map(([service, healthy], i) => (
              <motion.div
                key={service}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05, duration: 0.25 }}
                className="flex justify-between items-center py-1"
              >
                <span className="text-text-dim text-xs uppercase tracking-wider">
                  {service.replace(/_/g, " ")}
                </span>
                <motion.span
                  key={`${service}-${healthy}`}
                  initial={{ scale: 1.3 }}
                  animate={{ scale: 1 }}
                  transition={{ duration: 0.2 }}
                  className={`text-xs font-bold ${healthy ? "text-accent-capturing" : "text-event-injection"}`}
                >
                  {healthy ? "ONLINE" : "DEGRADED"}
                </motion.span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
