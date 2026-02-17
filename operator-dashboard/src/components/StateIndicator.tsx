import { motion } from "framer-motion";

interface StateIndicatorProps {
  state: 'idle' | 'capturing' | 'paused' | 'stopped';
}

const STATE_COLORS: Record<string, { color: string; glow: string; speed: number }> = {
  idle:      { color: "#5588aa", glow: "rgba(85, 136, 170, 0.4)", speed: 4 },
  capturing: { color: "#00ff88", glow: "rgba(0, 255, 136, 0.5)", speed: 1.5 },
  paused:    { color: "#ffaa00", glow: "rgba(255, 170, 0, 0.4)", speed: 3 },
  stopped:   { color: "#6688ff", glow: "rgba(102, 136, 255, 0.4)", speed: 5 },
};

export function StateIndicator({ state }: StateIndicatorProps) {
  const { color, glow, speed } = STATE_COLORS[state];

  return (
    <motion.div
      className="w-3.5 h-3.5 rounded-full"
      title={`State: ${state}`}
      animate={{
        backgroundColor: color,
        boxShadow: [
          `0 0 8px ${glow}`,
          `0 0 20px ${glow}`,
          `0 0 8px ${glow}`,
        ],
        scale: [1, 1.15, 1],
      }}
      transition={{
        duration: speed,
        repeat: Infinity,
        ease: "easeInOut",
      }}
    />
  );
}
