import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useOperatorStore } from "../store/operatorStore";
import { StateIndicator } from "../components/StateIndicator";
import { useStateTheme } from "../hooks/useStateTheme";

function CounterBar({ label, value, color, barColor, maxValue }: {
  label: string;
  value: number;
  color: string;
  barColor: string;
  maxValue: number;
}) {
  const widthPercent = maxValue > 0 ? (value / maxValue) * 100 : 0;

  return (
    <div>
      <div className="flex justify-between items-baseline mb-1">
        <span className="text-text-dim text-xs">{label}</span>
        <motion.span
          key={value}
          className="text-text-primary font-bold text-sm tabular-nums"
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

export function VitalsPanel() {
  const { demoState, teamName, track, startedAt } = useOperatorStore();
  const counters = useOperatorStore((s) => s.counters);
  const theme = useStateTheme();
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (demoState === "capturing" && startedAt !== null) {
      const interval = setInterval(() => {
        setElapsed(Date.now() - startedAt * 1000);
      }, 100);
      return () => clearInterval(interval);
    } else {
      setElapsed(0);
    }
  }, [demoState, startedAt]);

  const formatElapsed = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const total = counters.attacks + counters.clean;
  const shieldPercent = total > 0 ? Math.round((counters.clean / total) * 100) : 100;
  const shieldColor =
    shieldPercent >= 80 ? "#00ff88" :
    shieldPercent >= 50 ? "#ffaa00" : "#ff4444";

  const maxCounter = Math.max(counters.frames, counters.transcripts, counters.attacks, 1);

  return (
    <div className="glass-panel p-4 flex flex-col gap-4 flex-1 animate-border-glow">
      <h2 className="section-label">VITALS</h2>

      {/* State + Team + Track */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <StateIndicator state={demoState} />
          <span className="neon-text font-semibold uppercase text-sm">
            {theme.label}
          </span>
        </div>
        <div className="text-text-secondary text-sm">
          {teamName || "\u2014"} / {track || "\u2014"}
        </div>
        <div className="text-text-primary font-mono text-3xl font-bold">
          {demoState === "capturing" ? formatElapsed(elapsed) : "00:00"}
        </div>
      </div>

      <div className="border-t border-text-dim/20" />

      {/* Counters */}
      <div className="space-y-3">
        <CounterBar label="Frames" value={counters.frames} color="#00ccff" barColor="bg-event-transcript" maxValue={maxCounter} />
        <CounterBar label="Audio" value={counters.transcripts} color="#00ff88" barColor="bg-event-verified" maxValue={maxCounter} />
        <CounterBar label="Threats" value={counters.attacks} color="#ff4444" barColor="bg-event-injection" maxValue={maxCounter} />
      </div>

      <div className="border-t border-text-dim/20" />

      {/* Shield */}
      <div>
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
  );
}
