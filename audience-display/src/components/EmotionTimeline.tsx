import { AnimatePresence, motion } from "framer-motion";
import { useDisplayStore, type ActiveScreen } from "../store/displayStore";
import { emotionConfig, defaultVisuals } from "../lib/emotionConfig";
import { useEffect, useRef } from "react";

const VISIBLE_SCREENS: Set<ActiveScreen> = new Set([
  "commentary",
  "question",
  "scorecard",
]);

const MIN_HEIGHT = 20;
const MAX_HEIGHT = 48;

export function EmotionTimeline() {
  const activeScreen = useDisplayStore((s) => s.activeScreen);
  const sentences = useDisplayStore((s) => s.commentarySentences);
  const scrollRef = useRef<HTMLDivElement>(null);
  const visible = VISIBLE_SCREENS.has(activeScreen);

  // Auto-scroll to latest bar
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
    }
  }, [sentences.length]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="emotion-timeline"
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 64 }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.3, ease: "easeInOut" }}
          className="relative flex items-end gap-1 px-4 overflow-hidden shrink-0"
        >
          {/* Label */}
          <span className="text-[10px] tracking-widest uppercase text-arbiter-muted absolute top-1 left-4 z-10">
            Emotional Arc
          </span>

          {/* Scrollable bar container */}
          <div
            ref={scrollRef}
            className="flex items-end gap-1 overflow-x-auto w-full pt-4 scrollbar-hide"
          >
            {sentences.map((s, i) => {
              const visuals = emotionConfig[s.emotion] ?? defaultVisuals;
              const barHeight =
                MIN_HEIGHT + visuals.intensity * (MAX_HEIGHT - MIN_HEIGHT);

              return (
                <motion.div
                  key={i}
                  initial={{ scaleY: 0, opacity: 0 }}
                  animate={{ scaleY: 1, opacity: 1 }}
                  transition={{ duration: 0.3, ease: "easeOut" }}
                  className="shrink-0 rounded-sm origin-bottom"
                  style={{
                    width: 10,
                    height: barHeight,
                    backgroundColor: visuals.primary,
                    boxShadow: `0 0 8px ${visuals.secondary}`,
                  }}
                />
              );
            })}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
