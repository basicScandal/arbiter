import { motion, AnimatePresence } from "framer-motion";
import { useRef, useState, useEffect } from "react";
import { useDisplayStore } from "../store/displayStore";
import { RankingRow } from "./components/RankingRow";
import { NarrativeBlock } from "./components/NarrativeBlock";

export function DeliberationScreen() {
  const rankings = useDisplayStore((s) => s.rankings);
  const narrative = useDisplayStore((s) => s.narrative);

  // Rankings arrive worst-first (highest rank number first, rank 1 last).
  // We display them in arrival order (no sorting).
  // The last entry to arrive with rank === 1 gets the winner treatment.
  const lastEntry = rankings[rankings.length - 1];
  const winnerId = lastEntry?.rank === 1 ? lastEntry.rank : null;

  // Scan line on ranking arrival
  const prevRankingsCount = useRef(rankings.length);
  const [scanKey, setScanKey] = useState(0);
  const [scanIsWinner, setScanIsWinner] = useState(false);

  useEffect(() => {
    if (rankings.length > prevRankingsCount.current) {
      const newEntry = rankings[rankings.length - 1];
      setScanIsWinner(newEntry?.rank === 1);
      setScanKey((k) => k + 1);
    }
    prevRankingsCount.current = rankings.length;
  }, [rankings]);

  return (
    <div className="relative flex flex-col items-center h-full px-16 py-10 gap-8">
      {/* Ranking arrival scan line */}
      <AnimatePresence>
        {scanKey > 0 && (
          <motion.div
            key={`scan-${scanKey}`}
            className="absolute left-0 right-0 pointer-events-none"
            style={{
              height: "2px",
              background: scanIsWinner
                ? "linear-gradient(90deg, transparent 0%, #ffd700 30%, #ffd700 70%, transparent 100%)"
                : "linear-gradient(90deg, transparent 0%, #00d4ff 30%, #00d4ff 70%, transparent 100%)",
              boxShadow: scanIsWinner
                ? "0 0 12px #ffd700, 0 0 4px #ffd700"
                : "0 0 12px #00d4ff, 0 0 4px #00d4ff",
            }}
            initial={{ top: "10%", opacity: 0.9 }}
            animate={{ top: "95%", opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
          />
        )}
      </AnimatePresence>

      <motion.h2
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-3xl text-arbiter-accent tracking-widest uppercase"
      >
        Final Deliberation
      </motion.h2>

      {rankings.length > 0 && (
        <div className="w-full max-w-5xl overflow-y-auto min-h-0 flex-1">
        <table className="w-full">
          <thead>
            <tr className="text-lg text-arbiter-muted uppercase tracking-wider border-b border-arbiter-accent/20">
              <th className="pb-3 text-center w-20">Rank</th>
              <th className="pb-3 text-left">Team</th>
              <th className="pb-3 text-center">Score</th>
              <th className="pb-3 text-left">Track</th>
              <th className="pb-3 text-left">Reasoning</th>
            </tr>
          </thead>
          <tbody>
            {rankings.map((entry, i) => (
              <RankingRow
                key={`${entry.rank}-${entry.teamName}`}
                entry={entry}
                index={i}
                isWinner={winnerId !== null && entry.rank === 1}
              />
            ))}
          </tbody>
        </table>
        </div>
      )}

      {narrative && <NarrativeBlock text={narrative} />}
    </div>
  );
}
