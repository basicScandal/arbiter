import { motion } from "framer-motion";
import { useDisplayStore } from "../store/displayStore";
import { scoreColor } from "../lib/scoreColor";

export function IntermissionScreen() {
  const data = useDisplayStore((s) => s.intermissionData);

  if (!data) return null;

  const sorted = [...data.leaderboard].sort((a, b) => b.totalScore - a.totalScore);

  return (
    <div className="flex flex-col items-center h-full px-16 py-10 gap-8 overflow-auto">
      {/* Title */}
      <motion.h2
        initial={{ opacity: 0, y: -15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-4xl text-arbiter-accent tracking-widest uppercase font-black"
      >
        Leaderboard
      </motion.h2>

      {/* Injection counter badge */}
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.2, duration: 0.4 }}
        className="flex items-center gap-3 px-6 py-3 rounded border border-red-500/60 bg-red-950/40"
      >
        <span className="text-3xl font-black text-red-400">{data.totalInjections}</span>
        <span className="text-lg text-red-300/80 tracking-wider uppercase">
          Injection Attempts Blocked
        </span>
      </motion.div>

      {/* Leaderboard table */}
      {sorted.length > 0 && (
        <table className="w-full max-w-4xl">
          <thead>
            <tr className="text-base text-arbiter-muted uppercase tracking-wider border-b border-arbiter-accent/20">
              <th className="pb-3 text-center w-20">Rank</th>
              <th className="pb-3 text-left">Team</th>
              <th className="pb-3 text-center">Score</th>
              <th className="pb-3 text-left">Track</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((entry, i) => (
              <motion.tr
                key={entry.teamName}
                initial={{ opacity: 0, x: -30 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 + i * 0.1, duration: 0.4, ease: "easeOut" }}
                className="border-b border-arbiter-accent/10"
              >
                <td className="py-4 pr-4 text-2xl font-bold text-arbiter-accent text-center w-20">
                  #{i + 1}
                </td>
                <td className="py-4 pr-4 text-2xl text-arbiter-text font-medium">
                  {entry.teamName}
                </td>
                <td
                  className="py-4 pr-4 text-2xl font-bold text-center"
                  style={{ color: scoreColor(entry.totalScore) }}
                >
                  {entry.totalScore.toFixed(1)}
                </td>
                <td className="py-4 text-lg text-arbiter-muted">
                  {entry.track}
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Next demo incoming */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: [0.4, 1, 0.4] }}
        transition={{ delay: 0.8, duration: 2, repeat: Infinity, ease: "easeInOut" }}
        className="mt-auto text-2xl text-arbiter-muted tracking-widest uppercase"
      >
        Next Demo Incoming...
      </motion.p>
    </div>
  );
}
