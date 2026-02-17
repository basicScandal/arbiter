import { motion } from "framer-motion";
import { useOperatorStore } from "../store/operatorStore";

function CounterBar({ label, value, color, barColor }: {
  label: string;
  value: number;
  color: string;
  barColor: string;
}) {
  const counters = useOperatorStore((s) => s.counters);
  const maxValue = Math.max(
    counters.frames,
    counters.transcripts,
    counters.attacks,
    counters.clean,
    1,
  );
  const widthPercent = (value / maxValue) * 100;

  return (
    <div className="mb-3">
      <div className="flex justify-between items-baseline mb-1">
        <span className="text-text-dim text-xs">{label}</span>
        <motion.span
          key={value}
          className="text-text-primary font-bold text-lg tabular-nums"
          initial={{ scale: 1.4, color }}
          animate={{ scale: 1, color: "#e0e0f0" }}
          transition={{ duration: 0.3 }}
        >
          {value}
        </motion.span>
      </div>
      <div className="w-full bg-void rounded-full h-1.5 overflow-hidden">
        <motion.div
          className={`h-full ${barColor} rounded-full`}
          initial={false}
          animate={{ width: `${widthPercent}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          style={{ boxShadow: `0 0 8px ${color}` }}
        />
      </div>
    </div>
  );
}

export function CountersPanel() {
  const counters = useOperatorStore((s) => s.counters);

  return (
    <div className="glass-panel p-4 animate-border-glow">
      <h2 className="section-label mb-3">VITALS</h2>
      <CounterBar label="Frames" value={counters.frames} color="#00ccff" barColor="bg-event-transcript" />
      <CounterBar label="Transcripts" value={counters.transcripts} color="#00ff88" barColor="bg-event-verified" />
      <CounterBar label="Attacks" value={counters.attacks} color="#ff4444" barColor="bg-event-injection" />
      <CounterBar label="Clean" value={counters.clean} color="#ffd700" barColor="bg-arbiter-gold" />
    </div>
  );
}
