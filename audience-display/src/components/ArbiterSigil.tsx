import { motion, AnimatePresence, useAnimationControls } from "framer-motion";
import { useMemo, useEffect, useRef, useState } from "react";
import {
  emotionConfig,
  defaultVisuals,
  type EmotionVisuals,
} from "../lib/emotionConfig";

interface ArbiterSigilProps {
  activeScreen: string;
  emotion?: string;
  sentenceCount: number;
  injectionAlert: boolean;
  hasScoreTotal: boolean;
  className?: string;
}

interface SigilState {
  outerDuration: number;
  opacity: number;
  coreCycleDuration: number;
  color: EmotionVisuals;
  coreScale: [number, number, number];
}

function getSigilState(
  activeScreen: string,
  emotion?: string,
  injectionAlert?: boolean,
): SigilState {
  if (injectionAlert) {
    return {
      outerDuration: 2,
      opacity: 1.0,
      coreCycleDuration: 0.3,
      color: { primary: "#ff4444", secondary: "#ff0000", intensity: 1.0 },
      coreScale: [0.9, 1.1, 0.9],
    };
  }

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
  sentenceCount,
  injectionAlert,
  hasScoreTotal,
  className,
}: ArbiterSigilProps) {
  const state = getSigilState(activeScreen, emotion, injectionAlert);
  const dashArray = useMemo(() => outerRingDashArray(180, 12), []);
  const coreControls = useAnimationControls();
  const prevScreenRef = useRef(activeScreen);
  const prevSentenceCountRef = useRef(sentenceCount);
  const prevScoreTotalRef = useRef(hasScoreTotal);

  // Shockwave counter — incremented to trigger one-shot shockwave rings
  const [shockwaveKey, setShockwaveKey] = useState(0);

  // Shatter state for injection alerts
  const [shattered, setShattered] = useState(false);

  // Score burst counter
  const [scoreBurstKey, setScoreBurstKey] = useState(0);

  // Speaking pulse — fire on new sentence during commentary
  useEffect(() => {
    if (
      sentenceCount > prevSentenceCountRef.current &&
      activeScreen === "commentary"
    ) {
      coreControls.start({
        scale: [1.0, 1.15, 1.0],
        transition: { duration: 0.5, times: [0, 0.3, 1], ease: "easeOut" },
      });
    }
    prevSentenceCountRef.current = sentenceCount;
  }, [sentenceCount, activeScreen, coreControls]);

  // Shockwave on thinking entry
  useEffect(() => {
    if (activeScreen === "thinking" && prevScreenRef.current !== "thinking") {
      setShockwaveKey((k) => k + 1);
    }
    prevScreenRef.current = activeScreen;
  }, [activeScreen]);

  // Injection shatter
  useEffect(() => {
    if (injectionAlert) {
      setShattered(true);
    } else if (shattered) {
      // Delay reassembly for smooth animation
      const timer = setTimeout(() => setShattered(false), 800);
      return () => clearTimeout(timer);
    }
  }, [injectionAlert, shattered]);

  // Gold burst on score total
  useEffect(() => {
    if (hasScoreTotal && !prevScoreTotalRef.current) {
      setScoreBurstKey((k) => k + 1);
      coreControls.start({
        scale: [1.0, 1.3, 1.0],
        transition: { duration: 0.6, times: [0, 0.3, 1], ease: "easeOut" },
      });
    }
    prevScoreTotalRef.current = hasScoreTotal;
  }, [hasScoreTotal, coreControls]);

  const glowSize = Math.round(8 + state.color.intensity * 24);
  const glowColor = state.color.primary;

  // Ring displacement for shatter effect
  const shatterOffset = shattered ? 30 : 0;

  const isQuestion = activeScreen === "question";

  return (
    <div className={className}>
      <svg viewBox="0 0 400 400" className="w-80 h-80">
        {/* Shockwave ring — one-shot expanding circle */}
        <AnimatePresence>
          {shockwaveKey > 0 && (
            <motion.circle
              key={`shockwave-${shockwaveKey}`}
              cx={200}
              cy={200}
              fill="none"
              stroke="#00d4ff"
              strokeWidth={2}
              initial={{ r: 60, opacity: 0.8 }}
              animate={{ r: 200, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            />
          )}
        </AnimatePresence>

        {/* Score burst ring — gold expanding circle */}
        <AnimatePresence>
          {scoreBurstKey > 0 && (
            <motion.circle
              key={`scoreburst-${scoreBurstKey}`}
              cx={200}
              cy={200}
              fill="none"
              stroke="#ffd700"
              strokeWidth={3}
              initial={{ r: 60, opacity: 1 }}
              animate={{ r: 220, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.7, ease: "easeOut" }}
            />
          )}
        </AnimatePresence>

        {/* Outer ring — dashed, rotating, shatters outward on injection */}
        <motion.circle
          cx={200}
          cy={200}
          r={180}
          fill="none"
          strokeWidth={injectionAlert ? 3 : 2}
          strokeDasharray={dashArray}
          strokeLinecap="round"
          animate={{
            rotate: 360,
            stroke: state.color.primary,
            opacity: state.opacity,
            scale: shattered ? 1.15 : 1,
          }}
          transition={{
            rotate: {
              duration: state.outerDuration,
              repeat: Infinity,
              ease: "linear",
            },
            stroke: { duration: 0.6 },
            opacity: { duration: 0.6 },
            scale: { duration: shattered ? 0.2 : 0.8, ease: "easeOut" },
          }}
          style={{ originX: "200px", originY: "200px" }}
        />

        {/* Middle ring — solid, color-reactive, displaces on shatter */}
        <motion.circle
          cx={200}
          cy={200}
          r={120}
          fill="none"
          strokeWidth={injectionAlert ? 2.5 : 1.5}
          animate={{
            stroke: state.color.primary,
            opacity: state.opacity,
            translateY: shattered ? -shatterOffset * 0.5 : 0,
            scale: shattered ? 1.1 : 1,
          }}
          transition={{
            stroke: { duration: 0.6 },
            opacity: { duration: 0.6 },
            translateY: { duration: shattered ? 0.15 : 0.8, ease: "easeOut" },
            scale: { duration: shattered ? 0.15 : 0.8, ease: "easeOut" },
          }}
          style={{ originX: "200px", originY: "200px" }}
        />

        {/* Inner core — diamond on question, circle otherwise */}
        {isQuestion ? (
          <motion.rect
            x={200 - 42}
            y={200 - 42}
            width={84}
            height={84}
            rx={4}
            strokeWidth={0}
            animate={{
              fill: state.color.primary,
              rotate: 45,
              scale: state.coreScale,
              opacity: state.opacity * 0.35,
            }}
            transition={{
              fill: { duration: 0.6 },
              rotate: { duration: 0.4, ease: "easeOut" },
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
        ) : (
          <motion.circle
            cx={200}
            cy={200}
            r={60}
            strokeWidth={0}
            animate={{
              fill: state.color.primary,
              scale: state.coreScale,
              opacity: state.opacity * 0.3,
              translateY: shattered ? shatterOffset * 0.3 : 0,
            }}
            transition={{
              fill: { duration: 0.6 },
              scale: {
                duration: state.coreCycleDuration,
                repeat: Infinity,
                ease: "easeInOut",
              },
              opacity: { duration: 0.6 },
              translateY: {
                duration: shattered ? 0.15 : 0.8,
                ease: "easeOut",
              },
            }}
            style={{
              originX: "200px",
              originY: "200px",
              filter: `drop-shadow(0 0 ${glowSize}px ${glowColor})`,
            }}
          />
        )}

        {/* Speaking pulse ring — expands on each new sentence */}
        <AnimatePresence>
          {activeScreen === "commentary" && sentenceCount > 0 && (
            <motion.circle
              key={`pulse-${sentenceCount}`}
              cx={200}
              cy={200}
              fill="none"
              stroke={state.color.primary}
              strokeWidth={1.5}
              initial={{ r: 60, opacity: 0.4 }}
              animate={{ r: 130, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            />
          )}
        </AnimatePresence>

        {/* Core speaking pulse — controlled imperatively via coreControls */}
        <motion.circle
          cx={200}
          cy={200}
          r={60}
          fill="none"
          stroke={state.color.primary}
          strokeWidth={1}
          initial={{ opacity: 0 }}
          animate={coreControls}
          style={{ originX: "200px", originY: "200px" }}
        />
      </svg>
    </div>
  );
}
