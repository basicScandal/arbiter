import { motion } from "framer-motion";
import { useMemo } from "react";
import {
  emotionConfig,
  defaultVisuals,
  type EmotionVisuals,
} from "../lib/emotionConfig";

interface ArbiterSigilProps {
  activeScreen: string;
  emotion?: string;
  className?: string;
}

interface SigilState {
  outerDuration: number;
  opacity: number;
  coreCycleDuration: number;
  color: EmotionVisuals;
  coreScale: [number, number, number];
}

function getSigilState(activeScreen: string, emotion?: string): SigilState {
  const emotionVisuals =
    emotion && emotionConfig[emotion] ? emotionConfig[emotion] : defaultVisuals;

  switch (activeScreen) {
    case "thinking":
      return {
        outerDuration: 4,
        opacity: 1.0,
        coreCycleDuration: 1.5,
        color: { primary: "#00d4ff", secondary: "#00d4ff", intensity: 0.8 },
        coreScale: [0.92, 1.08, 0.92],
      };

    case "commentary":
      return {
        outerDuration: Math.max(3, 12 - emotionVisuals.intensity * 10),
        opacity: 1.0,
        coreCycleDuration: Math.max(1, 3 - emotionVisuals.intensity * 2),
        color: emotionVisuals,
        coreScale: [0.93, 1.12, 0.93],
      };

    case "question":
      return {
        outerDuration: 10,
        opacity: 0.9,
        coreCycleDuration: 3,
        color: { primary: "#ff8c00", secondary: "#ff8c00", intensity: 0.6 },
        coreScale: [0.96, 1.04, 0.96],
      };

    case "scorecard":
      return {
        outerDuration: 20,
        opacity: 1.0,
        coreCycleDuration: 2.5,
        color: { primary: "#ffd700", secondary: "#ffd700", intensity: 0.7 },
        coreScale: [0.97, 1.03, 0.97],
      };

    case "deliberation":
      return {
        outerDuration: 8,
        opacity: 1.0,
        coreCycleDuration: 3,
        color: { primary: "#ffd700", secondary: "#00d4ff", intensity: 0.9 },
        coreScale: [0.95, 1.05, 0.95],
      };

    case "idle":
    case "intermission":
    default:
      return {
        outerDuration: 12,
        opacity: 0.4,
        coreCycleDuration: 4,
        color: defaultVisuals,
        coreScale: [0.95, 1.05, 0.95],
      };
  }
}

// Generate dashed segments for the outer ring
function outerRingDashArray(r: number, segments: number): string {
  const circumference = 2 * Math.PI * r;
  const segLen = circumference / segments;
  const dash = segLen * 0.6;
  const gap = segLen * 0.4;
  return `${dash} ${gap}`;
}

export function ArbiterSigil({
  activeScreen,
  emotion,
  className,
}: ArbiterSigilProps) {
  const state = getSigilState(activeScreen, emotion);
  const dashArray = useMemo(() => outerRingDashArray(180, 12), []);

  const glowSize = Math.round(8 + state.color.intensity * 24);
  const glowColor = state.color.primary;

  return (
    <div className={className}>
      <svg viewBox="0 0 400 400" className="w-80 h-80">
        {/* Outer ring — dashed, rotating */}
        <motion.circle
          cx={200}
          cy={200}
          r={180}
          fill="none"
          strokeWidth={2}
          strokeDasharray={dashArray}
          strokeLinecap="round"
          animate={{
            rotate: 360,
            stroke: state.color.primary,
            opacity: state.opacity,
          }}
          transition={{
            rotate: {
              duration: state.outerDuration,
              repeat: Infinity,
              ease: "linear",
            },
            stroke: { duration: 0.6 },
            opacity: { duration: 0.6 },
          }}
          style={{ originX: "200px", originY: "200px" }}
        />

        {/* Middle ring — solid, color-reactive */}
        <motion.circle
          cx={200}
          cy={200}
          r={120}
          fill="none"
          strokeWidth={1.5}
          animate={{
            stroke: state.color.primary,
            opacity: state.opacity,
          }}
          transition={{
            stroke: { duration: 0.6 },
            opacity: { duration: 0.6 },
          }}
        />

        {/* Inner core — filled, breathing */}
        <motion.circle
          cx={200}
          cy={200}
          r={60}
          strokeWidth={0}
          animate={{
            fill: state.color.primary,
            scale: state.coreScale,
            opacity: state.opacity * 0.3,
          }}
          transition={{
            fill: { duration: 0.6 },
            scale: {
              duration: state.coreCycleDuration,
              repeat: Infinity,
              ease: "easeInOut",
            },
            opacity: { duration: 0.6 },
          }}
          style={{
            originX: "200px",
            originY: "200px",
            filter: `drop-shadow(0 0 ${glowSize}px ${glowColor})`,
          }}
        />
      </svg>
    </div>
  );
}
