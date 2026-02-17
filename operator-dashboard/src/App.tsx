import { motion } from "framer-motion";
import { useOperatorSocket } from "./hooks/useOperatorSocket";
import { useStateTheme } from "./hooks/useStateTheme";
import { Header } from "./components/Header";
import { ReconnectBanner } from "./components/ReconnectBanner";
import { CommandBar } from "./components/CommandBar";
import { StatusPanel } from "./panels/StatusPanel";
import { EventStream } from "./panels/EventStream";
import { CountersPanel } from "./panels/CountersPanel";
import { DefensePanel } from "./panels/DefensePanel";
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
      <main className="flex-1 grid grid-cols-3 gap-4 p-4 overflow-hidden">
        <div className="col-span-2 flex flex-col gap-4">
          <motion.div {...panelEntrance(0.05)}>
            <StatusPanel />
          </motion.div>
          <motion.div className="flex-1 flex flex-col" {...panelEntrance(0.12)}>
            <EventStream />
          </motion.div>
        </div>
        <div className="flex flex-col gap-4">
          <motion.div {...panelEntrance(0.18)}>
            <CountersPanel />
          </motion.div>
          <motion.div {...panelEntrance(0.24)}>
            <DefensePanel />
          </motion.div>
          <motion.div {...panelEntrance(0.30)}>
            <HealthPanel />
          </motion.div>
          <motion.div {...panelEntrance(0.36)}>
            <ScorePanel />
          </motion.div>
        </div>
      </main>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.3 }}
      >
        <CommandBar />
      </motion.div>
    </div>
  );
}
