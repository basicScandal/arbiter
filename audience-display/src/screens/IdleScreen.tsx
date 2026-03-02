import { motion } from "framer-motion";

export function IdleScreen() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-8">
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8 }}
        className="text-2xl text-arbiter-accent/60 tracking-[0.3em] uppercase font-bold"
      >
        NEBULA:FOG 2026
      </motion.p>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3, duration: 0.8 }}
        className="text-5xl text-arbiter-muted/60 animate-glow-pulse tracking-wide bg-arbiter-bg/50 px-8 py-4 rounded-xl"
      >
        Awaiting next demo…
      </motion.p>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.4 }}
        transition={{ delay: 0.6, duration: 0.8 }}
        className="text-xl text-arbiter-muted/40 tracking-wider"
      >
        AI-Powered Judging System
      </motion.p>
    </div>
  );
}
