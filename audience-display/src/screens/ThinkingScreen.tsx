import { motion } from "framer-motion";
import { useDisplayStore } from "../store/displayStore";

export function ThinkingScreen() {
  const thinkingTeam = useDisplayStore((s) => s.thinkingTeam);

  return (
    <div className="flex flex-col items-center justify-center h-full gap-10">
      {/* Team name + track */}
      {thinkingTeam && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="flex flex-col items-center gap-2"
        >
          <p className="text-3xl text-arbiter-accent tracking-widest uppercase font-bold">
            {thinkingTeam.teamName}
          </p>
          <p className="text-lg text-arbiter-muted tracking-wider uppercase">
            {thinkingTeam.track}
          </p>
        </motion.div>
      )}

      {/* Main analyzing text */}
      <motion.div
        animate={{ opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        className="text-5xl font-black tracking-widest text-cyan-300 uppercase"
        style={{
          textShadow: "0 0 20px rgba(0,200,255,0.6), 0 0 40px rgba(0,200,255,0.3)",
        }}
      >
        ARBITER IS ANALYZING...
      </motion.div>

      {/* Animated dots */}
      <div className="flex gap-4">
        {[0, 1, 2, 3, 4].map((i) => (
          <motion.div
            key={i}
            className="w-3 h-3 rounded-full bg-cyan-400"
            animate={{ opacity: [0.2, 1, 0.2], scale: [0.8, 1.2, 0.8] }}
            transition={{
              duration: 1.4,
              repeat: Infinity,
              ease: "easeInOut",
              delay: i * 0.18,
            }}
            style={{ boxShadow: "0 0 8px rgba(0,200,255,0.6)" }}
          />
        ))}
      </div>

      {/* Scan-line progress bar */}
      <div className="w-80 h-1 bg-cyan-900/40 rounded overflow-hidden">
        <motion.div
          className="h-full bg-cyan-400 rounded"
          animate={{ x: ["-100%", "100%"] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
          style={{ boxShadow: "0 0 12px rgba(0,200,255,0.8)" }}
        />
      </div>

      {/* Subtle status text */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.5 }}
        transition={{ delay: 0.8, duration: 0.6 }}
        className="text-base text-arbiter-muted tracking-wider"
      >
        Processing demo output — stand by
      </motion.p>
    </div>
  );
}
