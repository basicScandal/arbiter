import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useOperatorStore } from "../store/operatorStore";

const TRACKS = [
  "SHADOW::VECTOR",
  "SENTINEL::MESH",
  "ZERO::PROOF",
  "ROGUE::AGENT",
];

interface ActionButton {
  label: string;
  action: string;
  color: string;
  hoverGlow: string;
}

const STATE_ACTIONS: Record<string, ActionButton[]> = {
  idle: [
    { label: "START", action: "start", color: "bg-accent-capturing/20 text-accent-capturing border border-accent-capturing/40", hoverGlow: "rgba(0,255,136,0.3)" },
  ],
  capturing: [
    { label: "STOP", action: "stop", color: "bg-event-injection/20 text-event-injection border border-event-injection/40", hoverGlow: "rgba(255,68,68,0.3)" },
    { label: "PAUSE", action: "pause", color: "bg-accent-paused/20 text-accent-paused border border-accent-paused/40", hoverGlow: "rgba(255,170,0,0.3)" },
  ],
  paused: [
    { label: "RESUME", action: "resume", color: "bg-accent-capturing/20 text-accent-capturing border border-accent-capturing/40", hoverGlow: "rgba(0,255,136,0.3)" },
    { label: "STOP", action: "stop", color: "bg-event-injection/20 text-event-injection border border-event-injection/40", hoverGlow: "rgba(255,68,68,0.3)" },
  ],
  stopped: [
    { label: "Q&A", action: "qa", color: "bg-event-commentary/20 text-event-commentary border border-event-commentary/40", hoverGlow: "rgba(255,204,0,0.3)" },
    { label: "DELIBERATE", action: "deliberate", color: "bg-accent-stopped/20 text-accent-stopped border border-accent-stopped/40", hoverGlow: "rgba(102,136,255,0.3)" },
    { label: "RESET", action: "reset", color: "bg-text-dim/20 text-text-secondary border border-text-dim/40", hoverGlow: "rgba(85,85,112,0.3)" },
  ],
};

export function CommandBar() {
  const demoState = useOperatorStore((s) => s.demoState);
  const sendCommand = useOperatorStore((s) => s.sendCommand);
  const lastCommandResult = useOperatorStore((s) => s.lastCommandResult);
  const [teamName, setTeamName] = useState("");
  const [track, setTrack] = useState(TRACKS[3]);

  const handleStart = () => {
    if (teamName.trim()) {
      sendCommand('start', { team_name: teamName.trim(), track });
    }
  };

  const actions = STATE_ACTIONS[demoState] ?? [];

  return (
    <div className="glass-panel-elevated mx-4 mb-4 px-5 py-3">
      <AnimatePresence>
        {lastCommandResult && (
          <motion.div
            initial={{ opacity: 0, height: 0, marginBottom: 0 }}
            animate={{ opacity: 1, height: "auto", marginBottom: 8 }}
            exit={{ opacity: 0, height: 0, marginBottom: 0 }}
            transition={{ duration: 0.2 }}
            className={`text-xs px-3 py-1.5 rounded overflow-hidden ${
              lastCommandResult.success
                ? 'text-accent-capturing bg-accent-capturing/10'
                : 'text-event-injection bg-event-injection/10'
            }`}
          >
            {lastCommandResult.message}
          </motion.div>
        )}
      </AnimatePresence>
      <div className="flex items-center gap-3">
        <span className="neon-text text-sm font-bold shrink-0">arbiter&gt;</span>

        <AnimatePresence mode="wait">
          <motion.div
            key={demoState}
            className="flex items-center gap-3 flex-1"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            {demoState === 'idle' && (
              <>
                <input
                  type="text"
                  value={teamName}
                  onChange={(e) => setTeamName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleStart(); }}
                  placeholder="Team name..."
                  className="px-3 py-2 bg-surface-elevated border border-[var(--border-accent)] rounded-lg text-text-primary font-mono text-sm flex-1 outline-none focus:neon-border transition-all"
                />
                <select
                  value={track}
                  onChange={(e) => setTrack(e.target.value)}
                  className="px-3 py-2 bg-surface-elevated border border-[var(--border-accent)] rounded-lg text-text-primary font-mono text-xs"
                >
                  {TRACKS.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </>
            )}

            {actions.map((btn) => (
              <motion.button
                key={btn.action}
                whileTap={{ scale: 0.93 }}
                whileHover={{ boxShadow: `0 0 16px ${btn.hoverGlow}` }}
                onClick={() => {
                  if (btn.action === 'start') handleStart();
                  else sendCommand(btn.action);
                }}
                disabled={btn.action === 'start' && !teamName.trim()}
                className={`px-5 py-2 font-bold text-sm rounded-lg transition-colors duration-200 disabled:opacity-30 disabled:cursor-not-allowed ${btn.color}`}
              >
                {btn.label}
              </motion.button>
            ))}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
