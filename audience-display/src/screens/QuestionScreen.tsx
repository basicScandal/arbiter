import { motion } from "framer-motion";
import { useDisplayStore } from "../store/displayStore";

export function QuestionScreen() {
  const teamName = useDisplayStore((s) => s.teamName);
  const text = useDisplayStore((s) => s.commentaryText);

  return (
    <div className="flex flex-col items-center justify-center h-full px-16 gap-8">
      {teamName && (
        <motion.h2
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-2xl text-arbiter-accent tracking-widest uppercase"
        >
          {teamName}
        </motion.h2>
      )}
      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15, duration: 0.5 }}
        className="text-5xl text-arbiter-orange italic leading-snug text-center max-w-5xl"
      >
        <span className="font-bold not-italic">Q: </span>
        {text}
      </motion.p>
    </div>
  );
}
