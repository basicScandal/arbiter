import { AnimatePresence, motion } from "framer-motion";
import { useDisplayStore } from "../store/displayStore";
import { IdleScreen } from "../screens/IdleScreen";
import { CommentaryScreen } from "../screens/CommentaryScreen";
import { QuestionScreen } from "../screens/QuestionScreen";
import { ScoreCardScreen } from "../screens/ScoreCardScreen";
import { DeliberationScreen } from "../screens/DeliberationScreen";
import { ThinkingScreen } from "../screens/ThinkingScreen";
import { IntermissionScreen } from "../screens/IntermissionScreen";
import { SigilBackground } from "./SigilBackground";

const screenMap = {
  idle: IdleScreen,
  commentary: CommentaryScreen,
  question: QuestionScreen,
  scorecard: ScoreCardScreen,
  deliberation: DeliberationScreen,
  thinking: ThinkingScreen,
  intermission: IntermissionScreen,
} as const;

export function ScreenRouter() {
  const activeScreen = useDisplayStore((s) => s.activeScreen);
  const Screen = screenMap[activeScreen];

  return (
    <div className="flex-1 overflow-hidden relative">
      <SigilBackground />
      <AnimatePresence mode="wait">
        <motion.div
          key={activeScreen}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.4, ease: "easeInOut" }}
          className="absolute inset-0 overflow-auto z-10"
        >
          <Screen />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
