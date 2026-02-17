import { motion } from "framer-motion";
import { useDisplayStore } from "../store/displayStore";

export function CommentaryScreen() {
  const teamName = useDisplayStore((s) => s.teamName);
  const text = useDisplayStore((s) => s.commentaryText);

  return (
    <div className="flex flex-col items-center justify-center h-full px-12 gap-6">
      {teamName && (
        <motion.h2
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-lg text-arbiter-accent tracking-widest uppercase"
        >
          {teamName}
        </motion.h2>
      )}
      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15, duration: 0.5 }}
        className="text-3xl text-arbiter-text leading-relaxed text-center max-w-4xl"
      >
        {text}
      </motion.p>
    </div>
  );
}
