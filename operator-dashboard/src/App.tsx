import { motion } from "framer-motion";
import { useOperatorSocket } from "./hooks/useOperatorSocket";
import { useStateTheme } from "./hooks/useStateTheme";
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

export default function App() {
  useOperatorSocket();
  useStateTheme();

  return (
    <div className="flex flex-col h-screen bg-void font-mono">
      <ReconnectBanner />
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <Header />
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
