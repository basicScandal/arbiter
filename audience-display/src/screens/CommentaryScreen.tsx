import { motion, AnimatePresence } from "framer-motion";
import { useDisplayStore } from "../store/displayStore";

const emotionStyles: Record<string, string> = {
  // Warm / positive
  excited: "text-green-300",
  amazed: "text-cyan-300",
  impressed: "text-cyan-300",
  proud: "text-yellow-300",
  encouraging: "text-green-300",
  supportive: "text-cyan-200",
  content: "text-arbiter-text",
  // Cool / analytical
  confident: "text-cyan-200",
  thoughtful: "text-violet-300",
  curious: "text-orange-300",
  constructive: "text-green-200",
  // Edge / negative
  sarcastic: "text-yellow-200/90",
  ironic: "text-orange-300",
  skeptical: "text-orange-300",
  disappointed: "text-red-300/80",
  surprised: "text-violet-300",
  // Misc
  humorous: "text-amber-200",
  concerned: "text-orange-300",
  default: "text-arbiter-text",
};

const emotionGlow: Record<string, string> = {
  sarcastic: "drop-shadow-[0_0_8px_rgba(255,204,0,0.3)]",
  amazed: "drop-shadow-[0_0_12px_rgba(0,200,255,0.4)]",
  impressed: "drop-shadow-[0_0_12px_rgba(0,200,255,0.4)]",
  disappointed: "drop-shadow-[0_0_8px_rgba(255,68,68,0.3)]",
  proud: "drop-shadow-[0_0_8px_rgba(255,215,0,0.3)]",
  excited: "drop-shadow-[0_0_8px_rgba(0,255,136,0.3)]",
  surprised: "drop-shadow-[0_0_8px_rgba(123,97,255,0.3)]",
  default: "",
};

export function CommentaryScreen() {
  const teamName = useDisplayStore((s) => s.teamName);
  const sentences = useDisplayStore((s) => s.commentarySentences);

  return (
    <div
      className="flex h-full"
      aria-live="polite"
      aria-atomic="false"
    >
      {/* Left ~40% — sigil shows through from background layer */}
      <div className="w-2/5 shrink-0" />

      {/* Right ~60% — text content with semi-transparent backdrop */}
      <div className="flex-1 flex flex-col justify-end px-12 py-8 min-h-0">
        <div className="bg-arbiter-bg/70 rounded-2xl px-10 py-8 backdrop-blur-sm max-h-full flex flex-col overflow-hidden">
          {teamName && (
            <motion.h2
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-2xl text-arbiter-accent tracking-widest uppercase mb-6 shrink-0"
            >
              {teamName}
            </motion.h2>
          )}
          <div className="text-4xl leading-relaxed max-w-5xl font-medium space-y-1 overflow-y-auto min-h-0">
            <AnimatePresence>
              {sentences.map((s, i) => {
                const colorClass =
                  emotionStyles[s.emotion] ?? emotionStyles.default;
                const glowClass =
                  emotionGlow[s.emotion] ?? emotionGlow.default;
                return (
                  <motion.span
                    key={i}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: 0.05 }}
                    className={`inline ${colorClass} ${glowClass}`}
                  >
                    {s.text}{" "}
                  </motion.span>
                );
              })}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}
