import { motion } from "framer-motion";
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

  const layout = getSigilLayout(activeScreen);

  return (
    <div className="absolute inset-0 z-0 pointer-events-none flex items-center justify-center">
      <motion.div
        animate={{
          x: layout.x,
          y: layout.y,
          scale: layout.scale,
        }}
        transition={{
          duration: 0.8,
          ease: [0.25, 0.1, 0.25, 1], // cubic-bezier for smooth deceleration
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
        />
      </motion.div>
    </div>
  );
}
