import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useOperatorStore } from "../store/operatorStore";

const EVENT_CONFIG: Record<string, { icon: string; color: string; label?: string }> = {
  demo_started:         { icon: "\u25b6", color: "text-event-started",    label: "Demo started" },
  demo_stopped:         { icon: "\u25a0", color: "text-event-stopped",    label: "Demo stopped" },
  transcript_received:  { icon: "\u223c", color: "text-event-transcript", label: "Transcript" },
  key_frame_detected:   { icon: "\u25c9", color: "text-event-frame",     label: "Key frame" },
  injection_detected:   { icon: "\u26a0", color: "text-event-injection",  label: "INJECTION" },
  roast_generated:      { icon: "\u2734", color: "text-event-roast",      label: "Roast" },
  observation_verified: { icon: "\u2713", color: "text-event-verified",   label: "Verified" },
  commentary_delivered: { icon: "\u266b", color: "text-event-commentary", label: "Commentary" },
  scoring_complete:     { icon: "\u2605", color: "text-event-commentary", label: "Scored" },
  scoring_failed:       { icon: "\u2716", color: "text-event-injection",  label: "Score FAILED" },
  qa_requested:         { icon: "?",      color: "text-accent-paused",    label: "Q&A" },
  tts_speaking:         { icon: "\u25b8", color: "text-event-tts",        label: "Speaking" },
  tts_finished:         { icon: "\u2014", color: "text-event-tts",        label: "TTS done" },
};

const eventVariants = {
  initial: { opacity: 0, x: -20 },
  animate: (opacity: number) => ({
    opacity,
    x: 0,
    transition: { duration: 0.35, ease: "easeOut" as const },
  }),
  exit: { opacity: 0, x: -10, transition: { duration: 0.15 } },
};

const commentaryVariants = {
  initial: { opacity: 0, scale: 0.95, y: -4 },
  animate: (opacity: number) => ({
    opacity,
    scale: 1,
    y: 0,
    transition: { duration: 0.4, ease: "easeOut" as const },
  }),
  exit: { opacity: 0, scale: 0.95, transition: { duration: 0.2 } },
};

function formatEventData(eventType: string, data?: Record<string, unknown>): string {
  if (!data) {
    // Static labels for data-less events
    if (eventType === "key_frame_detected") return "Key frame captured";
    if (eventType === "tts_speaking") return "Speaking...";
    if (eventType === "tts_finished") return "Speech complete";
    return "";
  }
  if (eventType === "commentary_delivered" && data.text) {
    const text = String(data.text);
    return text.length > 120 ? text.slice(0, 117) + "..." : text;
  }
  if (eventType === "roast_generated" && data.text) {
    const text = String(data.text);
    return text.length > 70 ? text.slice(0, 67) + "..." : text;
  }
  if (eventType === "transcript_received" && data.segment) {
    const seg = data.segment as Record<string, unknown>;
    const text = String(seg.text || "");
    return text.length > 80 ? text.slice(0, 77) + "..." : text;
  }
  if (eventType === "injection_detected" && data.attempt) {
    const att = data.attempt as Record<string, unknown>;
    return `${att.injection_type} (${att.confidence})`;
  }
  if (eventType === "observation_verified") {
    const obs = data.observations;
    const atk = data.injection_attempts;
    if (Array.isArray(obs) || typeof obs === "number") {
      const nObs = Array.isArray(obs) ? obs.length : obs;
      const nAtk = Array.isArray(atk) ? atk.length : (atk ?? 0);
      return `${nObs} observations, ${nAtk} attacks filtered`;
    }
  }
  if (eventType === "scoring_complete" && data.scorecard) {
    const sc = data.scorecard as Record<string, unknown>;
    return `${sc.team_name}: ${Number(sc.total_score).toFixed(1)}/10`;
  }
  if (eventType === "scoring_failed") {
    const error = data.error ? String(data.error) : "unknown error";
    return `${data.team_name}: ${error.length > 80 ? error.slice(0, 77) + "..." : error}`;
  }
  if (data.team_name) return String(data.team_name);
  return "";
}

export function NeuralFeed() {
  const events = useOperatorStore((s) => s.events);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [events]);

  const formatTimestamp = (ts: number) => {
    const date = new Date(ts * 1000);
    return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div className="glass-panel p-4 flex-1 overflow-hidden flex flex-col animate-border-glow">
      <h2 className="section-label mb-3">NEURAL FEED</h2>
      <div ref={scrollRef} role="log" aria-live="polite" className="flex-1 overflow-y-auto space-y-0.5 font-mono text-sm">
        {events.length === 0 ? (
          <div className="text-text-dim text-center py-8">Awaiting neural activity...</div>
        ) : (
          <AnimatePresence initial={false}>
            {events.map((evt, i) => {
              const config = EVENT_CONFIG[evt.event_type] ?? { icon: "\u00b7", color: "text-text-dim", label: evt.event_type };
              const opacity = i < 3 ? 1.0 : i < 8 ? 0.75 : i < 15 ? 0.5 : 0.35;
              const detail = formatEventData(evt.event_type, evt.data);
              const isCommentary = evt.event_type === "commentary_delivered";
              const isInjection = evt.event_type === "injection_detected";

              if (isCommentary && detail) {
                return (
                  <motion.div
                    key={evt.id}
                    custom={opacity}
                    variants={commentaryVariants}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    className="glass-panel-elevated px-3 py-2 my-1 border-l-2"
                    style={{ borderLeftColor: 'var(--color-event-commentary)' }}
                  >
                    <div className="flex gap-2 items-baseline mb-1">
                      <span className="text-text-dim text-xs">{formatTimestamp(evt.timestamp)}</span>
                      <span className={`${config.color} font-semibold`}>{config.icon} {config.label}</span>
                    </div>
                    <p className="text-text-primary text-sm leading-relaxed">{detail}</p>
                  </motion.div>
                );
              }

              if (evt.event_type === "roast_generated" && detail) {
                return (
                  <motion.div
                    key={evt.id}
                    custom={opacity}
                    variants={commentaryVariants}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    className="glass-panel-elevated px-3 py-2 my-1 border-l-2"
                    style={{ borderLeftColor: 'var(--color-event-roast)' }}
                  >
                    <div className="flex gap-2 items-baseline mb-1">
                      <span className="text-text-dim text-xs">{formatTimestamp(evt.timestamp)}</span>
                      <span className={`${config.color} font-semibold`}>{config.icon} {config.label}</span>
                    </div>
                    <p className="text-event-roast text-sm leading-relaxed italic">{detail}</p>
                  </motion.div>
                );
              }

              if (isInjection) {
                return (
                  <motion.div
                    key={evt.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{
                      opacity,
                      x: 0,
                      borderColor: [
                        "rgba(255,68,68,0.5)",
                        "rgba(255,68,68,0.15)",
                        "rgba(255,68,68,0.5)",
                      ],
                    }}
                    exit={{ opacity: 0, x: -10 }}
                    transition={{
                      opacity: { duration: 0.35 },
                      x: { duration: 0.35 },
                      borderColor: { duration: 0.8, repeat: 2 },
                    }}
                    className="flex gap-3 py-1 px-2 rounded bg-event-injection/5 border border-event-injection/30"
                  >
                    <span className="text-text-dim shrink-0 text-xs tabular-nums">
                      {formatTimestamp(evt.timestamp)}
                    </span>
                    <span className={`${config.color} shrink-0`}>
                      {config.icon}
                    </span>
                    <span className={`${config.color} font-semibold shrink-0 text-xs`}>
                      {config.label}
                    </span>
                    {detail && (
                      <span className="text-text-secondary truncate text-xs">
                        {detail}
                      </span>
                    )}
                  </motion.div>
                );
              }

              return (
                <motion.div
                  key={evt.id}
                  custom={opacity}
                  variants={eventVariants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                  className="flex gap-3 py-1 px-2 rounded"
                >
                  <span className="text-text-dim shrink-0 text-xs tabular-nums">
                    {formatTimestamp(evt.timestamp)}
                  </span>
                  <span className={`${config.color} shrink-0`}>
                    {config.icon}
                  </span>
                  <span className={`${config.color} font-semibold shrink-0 text-xs`}>
                    {config.label}
                  </span>
                  {detail && (
                    <span className="text-text-secondary truncate text-xs">
                      {detail}
                    </span>
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
