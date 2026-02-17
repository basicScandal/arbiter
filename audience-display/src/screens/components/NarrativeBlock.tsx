import { motion } from "framer-motion";

interface NarrativeBlockProps {
  text: string;
}

export function NarrativeBlock({ text }: NarrativeBlockProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.8 }}
      className="mt-8 px-8 py-6 bg-arbiter-surface/50 rounded-lg border border-arbiter-accent/10 max-w-4xl mx-auto"
    >
      <p className="text-xl text-arbiter-text leading-relaxed whitespace-pre-wrap">
        {text}
      </p>
    </motion.div>
  );
}
