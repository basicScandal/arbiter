import { motion, AnimatePresence } from "framer-motion";
import { useDisplayStore } from "../store/displayStore";
import { ArbiterSigil } from "./ArbiterSigil";

interface SigilLayout {
  x: string; // CSS translate percentage from center
  y: string;
  scale: number;
}

function getSigilLayout(screen: string): SigilLayout {
  switch (screen) {
    case "commentary":
      // Left-center — sigil as "speaker portrait"
      return { x: "-30%", y: "0%", scale: 0.75 };
    case "scorecard":
      // Upper area — seal of judgment above scores
      return { x: "0%", y: "10%", scale: 0.7 };
    case "deliberation":
      // Centered but shifted down to sit between header and rankings
      return { x: "0%", y: "15%", scale: 0.75 };
    case "intermission":
      // Lower area — leaderboard dominates
      return { x: "0%", y: "25%", scale: 0.5 };
    case "thinking":
      // Centered, slightly above middle
      return { x: "0%", y: "-5%", scale: 1.0 };
    case "idle":
    case "question":
    default:
      // Dead center
      return { x: "0%", y: "0%", scale: 1.0 };
  }
}

export function SigilBackground() {
  const activeScreen = useDisplayStore((s) => s.activeScreen);
  const sentences = useDisplayStore((s) => s.commentarySentences);
  const injectionAlert = useDisplayStore((s) => s.injectionAlert);
  const scoreTotal = useDisplayStore((s) => s.scoreTotal);
  const rankings = useDisplayStore((s) => s.rankings);
  const criteria = useDisplayStore((s) => s.criteria);

  const latestEmotion =
    sentences.length > 0
      ? sentences[sentences.length - 1].emotion
      : undefined;

  const criteriaAvgScore =
    criteria.length > 0
      ? criteria.reduce((sum, c) => sum + c.score, 0) / criteria.length
      : 0;

  const layout = getSigilLayout(activeScreen);

  return (
    <div className="absolute inset-0 z-0 pointer-events-none flex items-center justify-center">
      {/* Screen border flash — red glow on injection alert */}
      <AnimatePresence>
        {injectionAlert && (
          <motion.div
            key="border-flash"
            className="absolute inset-0 pointer-events-none"
            style={{
              boxShadow: "inset 0 0 60px 10px rgba(255, 68, 68, 0.6)",
            }}
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 1, 0.4] }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5, times: [0, 0.15, 1] }}
          />
        )}
      </AnimatePresence>

      {/* CRT scanline overlay — red interference on background layer */}
      <AnimatePresence>
        {injectionAlert && (
          <motion.div
            key="crt-scanlines"
            className="absolute inset-0 pointer-events-none"
            initial={{ opacity: 0.5 }}
            animate={{ opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            style={{
              background:
                "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,0,0,0.08) 2px, rgba(255,0,0,0.08) 4px)",
              mixBlendMode: "multiply",
            }}
          />
        )}
      </AnimatePresence>

      <motion.div
        animate={{
          x: injectionAlert
            ? [0, -12, 8, -5, 10, -7, 0]
            : layout.x,
          y: layout.y,
          scale: layout.scale,
        }}
        transition={{
          duration: 0.8,
          ease: [0.25, 0.1, 0.25, 1], // cubic-bezier for smooth deceleration
          x: injectionAlert
            ? { duration: 0.3, ease: "easeOut" }
            : undefined,
        }}
      >
        <ArbiterSigil
          activeScreen={activeScreen}
          emotion={latestEmotion}
          sentenceCount={sentences.length}
          injectionAlert={!!injectionAlert}
          hasScoreTotal={!!scoreTotal}
          hasWinnerRevealed={rankings.some((r) => r.rank === 1)}
          criteriaCount={criteria.length}
          rankingsCount={rankings.length}
          criteriaAvgScore={criteriaAvgScore}
        />
      </motion.div>
    </div>
  );
}
