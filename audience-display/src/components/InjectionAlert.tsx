import { motion, AnimatePresence } from "framer-motion";
import { useDisplayStore } from "../store/displayStore";

export function InjectionAlert() {
  const alert = useDisplayStore((s) => s.injectionAlert);

  return (
    <AnimatePresence>
      {alert && (
        <motion.div
          key="injection-alert"
          initial={{ opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 1.05 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center"
          style={{ background: "rgba(80, 0, 0, 0.88)" }}
        >
          {/* Pulsing backdrop glow */}
          <motion.div
            className="absolute inset-0 pointer-events-none"
            animate={{ opacity: [0.4, 0.7, 0.4] }}
            transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
            style={{
              background:
                "radial-gradient(ellipse at center, rgba(220,38,38,0.35) 0%, transparent 70%)",
            }}
          />

          {/* Content */}
          <div className="relative flex flex-col items-center gap-8 px-20 text-center">
            {/* Flash bar at top */}
            <motion.div
              className="absolute -top-16 left-0 right-0 h-2 bg-red-500"
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 0.6, repeat: Infinity }}
            />

            {/* Main header */}
            <motion.div
              className="text-6xl font-black tracking-widest text-white uppercase"
              animate={{ textShadow: ["0 0 20px rgba(239,68,68,0.8)", "0 0 40px rgba(239,68,68,1)", "0 0 20px rgba(239,68,68,0.8)"] }}
              transition={{ duration: 1, repeat: Infinity, ease: "easeInOut" }}
            >
              INJECTION ATTEMPT BLOCKED
            </motion.div>

            {/* Team name */}
            {alert.teamName && (
              <div className="text-2xl text-red-300/80 tracking-widest uppercase">
                {alert.teamName}
              </div>
            )}

            {/* Category + Confidence badges */}
            <div className="flex gap-4 items-center">
              <span className="px-4 py-2 rounded border-2 border-red-400 text-red-100 text-xl font-bold uppercase tracking-wider bg-red-900/60">
                {alert.category}
              </span>
              <span className="px-4 py-2 rounded border border-red-600/60 text-red-300 text-lg tracking-wider bg-red-950/50">
                Confidence: {alert.confidence}
              </span>
            </div>

            {/* Roast text */}
            <motion.p
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.4 }}
              className="text-2xl text-red-100/80 italic max-w-3xl leading-relaxed"
            >
              "{alert.roast}"
            </motion.p>

            {/* Bottom flash bar */}
            <motion.div
              className="absolute -bottom-16 left-0 right-0 h-2 bg-red-500"
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 0.6, repeat: Infinity, delay: 0.3 }}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
