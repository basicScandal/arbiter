import { AnimatePresence, motion } from "framer-motion";
import { useOperatorStore } from "../store/operatorStore";

export function ReconnectBanner() {
  const connectionState = useOperatorStore((s) => s.connectionState);
  const showBanner = connectionState === 'reconnecting';

  return (
    <AnimatePresence>
      {showBanner && (
        <motion.div
          initial={{ opacity: 0, y: -40 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -40 }}
          transition={{ duration: 0.3 }}
          role="alert"
          aria-live="assertive"
          className="fixed top-0 inset-x-0 z-50 bg-event-injection/90 text-white text-center py-2 font-mono text-sm tracking-widest"
        >
          CONNECTION LOST — RECONNECTING...
        </motion.div>
      )}
    </AnimatePresence>
  );
}
