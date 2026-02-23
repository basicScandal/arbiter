import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useDisplayStore, type ActiveScreen } from "../store/displayStore";

const SCREENS: { key: string; screen: ActiveScreen }[] = [
  { key: "1", screen: "idle" },
  { key: "2", screen: "thinking" },
  { key: "3", screen: "commentary" },
  { key: "4", screen: "question" },
  { key: "5", screen: "scorecard" },
  { key: "6", screen: "deliberation" },
  { key: "7", screen: "intermission" },
];

const AUTO_HIDE_MS = 3000;

export function ViewSwitcher() {
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const activeScreen = useDisplayStore((s) => s.activeScreen);
  const manualOverride = useDisplayStore((s) => s.manualOverride);
  const setManualScreen = useDisplayStore((s) => s.setManualScreen);
  const resumeLive = useDisplayStore((s) => s.resumeLive);

  const resetAutoHide = useCallback(() => {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setVisible(false), AUTO_HIDE_MS);
  }, []);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      // Backtick toggles overlay
      if (e.key === "`") {
        e.preventDefault();
        setVisible((v) => {
          if (!v) {
            // Opening — start auto-hide timer
            clearTimeout(timerRef.current);
            timerRef.current = setTimeout(() => setVisible(false), AUTO_HIDE_MS);
          } else {
            clearTimeout(timerRef.current);
          }
          return !v;
        });
        return;
      }

      // Number keys only work while overlay is visible
      if (!visible) return;

      if (e.key === "0") {
        e.preventDefault();
        resumeLive();
        resetAutoHide();
        return;
      }

      const entry = SCREENS.find((s) => s.key === e.key);
      if (entry) {
        e.preventDefault();
        setManualScreen(entry.screen);
        resetAutoHide();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      clearTimeout(timerRef.current);
    };
  }, [visible, setManualScreen, resumeLive, resetAutoHide]);

  const handleScreenClick = (screen: ActiveScreen) => {
    setManualScreen(screen);
    resetAutoHide();
  };

  const handleLiveClick = () => {
    resumeLive();
    resetAutoHide();
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="view-switcher"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="fixed bottom-6 right-6 z-[60] flex flex-col gap-2 rounded-xl border border-arbiter-accent/20 bg-arbiter-surface/95 p-3 backdrop-blur-md shadow-lg shadow-black/40"
          onMouseMove={resetAutoHide}
        >
          {/* LIVE toggle */}
          <button
            onClick={handleLiveClick}
            className={`w-full rounded-lg px-3 py-1.5 text-xs font-bold uppercase tracking-widest transition-colors ${
              !manualOverride
                ? "bg-arbiter-green/20 text-arbiter-green border border-arbiter-green/40"
                : "bg-transparent text-arbiter-accent/60 border border-arbiter-accent/20 hover:border-arbiter-accent/40"
            }`}
          >
            {!manualOverride ? "LIVE" : "RESUME LIVE"}
            <span className="ml-2 text-[10px] opacity-50">0</span>
          </button>

          {/* Divider */}
          <div className="h-px bg-arbiter-accent/10" />

          {/* Screen buttons grid */}
          <div className="grid grid-cols-2 gap-1.5">
            {SCREENS.map(({ key, screen }) => (
              <button
                key={screen}
                onClick={() => handleScreenClick(screen)}
                className={`rounded-lg px-2.5 py-1.5 text-[11px] font-mono uppercase tracking-wider transition-colors ${
                  activeScreen === screen && manualOverride
                    ? "bg-arbiter-accent/20 text-arbiter-accent border border-arbiter-accent/40"
                    : activeScreen === screen
                      ? "bg-arbiter-accent/10 text-arbiter-accent/70 border border-arbiter-accent/20"
                      : "bg-white/5 text-arbiter-muted/60 border border-transparent hover:bg-white/10 hover:text-arbiter-muted"
                }`}
              >
                <span className="mr-1.5 opacity-40">{key}</span>
                {screen}
              </button>
            ))}
          </div>

          {/* Mode indicator */}
          {manualOverride && (
            <div className="text-center text-[10px] uppercase tracking-widest text-arbiter-orange/70">
              manual override
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
