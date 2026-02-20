import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useOperatorSocket } from "./hooks/useOperatorSocket";
import { useOperatorStore } from "./store/operatorStore";
import { useStateTheme } from "./hooks/useStateTheme";
import { useAudioFeedback } from "./hooks/useAudioFeedback";
import { Header } from "./components/Header";
import { ReconnectBanner } from "./components/ReconnectBanner";
import { NeuralPrompt } from "./components/NeuralPrompt";
import { NeuralFeed } from "./panels/NeuralFeed";
import { DefenseStrip } from "./panels/DefenseStrip";
import { VitalsPanel } from "./panels/VitalsPanel";
import { HealthPanel } from "./panels/HealthPanel";
import { ScorePanel } from "./panels/ScorePanel";

const panelEntrance = (delay: number) => ({
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { delay, duration: 0.4, ease: "easeOut" as const },
});

function DemoTimerBanner() {
  const demoTimer = useOperatorStore((s) => s.demoTimer);
  const isCritical = demoTimer?.level === "critical";

  return (
    <AnimatePresence>
      {demoTimer && (
        <motion.div
          initial={{ opacity: 0, y: -40 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -40 }}
          transition={{ duration: 0.3 }}
          className={`fixed top-0 inset-x-0 z-40 text-white text-center py-2 font-mono text-sm tracking-widest ${
            isCritical
              ? "bg-red-600/90 animate-pulse"
              : "bg-yellow-600/90"
          }`}
        >
          {demoTimer.message}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default function App() {
  useOperatorSocket();
  useStateTheme();

  const [muted, setMuted] = useState(true);
  useAudioFeedback(muted);

  return (
    <div className="flex flex-col h-screen bg-void font-mono">
      <ReconnectBanner />
      <DemoTimerBanner />
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <Header muted={muted} onToggleMute={() => setMuted((m) => !m)} />
      </motion.div>
      <main className="flex-1 flex gap-4 p-4 overflow-hidden">
        {/* Left column — Neural Feed + Defense Strip */}
        <div className="flex-[2] flex flex-col gap-3">
          <motion.div className="flex-1 flex flex-col" {...panelEntrance(0.05)}>
            <NeuralFeed />
          </motion.div>
          <motion.div {...panelEntrance(0.12)}>
            <DefenseStrip />
          </motion.div>
        </div>
        {/* Right column — Vitals sidebar */}
        <div className="w-80 flex flex-col gap-3">
          <motion.div className="flex-1 flex flex-col" {...panelEntrance(0.08)}>
            <VitalsPanel />
          </motion.div>
          <motion.div {...panelEntrance(0.16)}>
            <HealthPanel />
          </motion.div>
          <motion.div {...panelEntrance(0.22)}>
            <ScorePanel />
          </motion.div>
        </div>
      </main>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25, duration: 0.3 }}
      >
        <NeuralPrompt />
      </motion.div>
    </div>
  );
}
