import { useEffect, useState } from "react";
import { useOperatorStore } from "../store/operatorStore";
import { StateIndicator } from "../components/StateIndicator";
import { useStateTheme } from "../hooks/useStateTheme";

export function StatusPanel() {
  const { demoState, teamName, track, startedAt } = useOperatorStore();
  const theme = useStateTheme();
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (demoState === 'capturing' && startedAt !== null) {
      const interval = setInterval(() => {
        setElapsed(Date.now() - startedAt * 1000);
      }, 100);
      return () => clearInterval(interval);
    } else {
      setElapsed(0);
    }
  }, [demoState, startedAt]);

  const formatElapsed = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="glass-panel p-4 animate-border-glow">
      <h2 className="section-label mb-3">STATUS</h2>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-text-dim text-xs mb-1">Team</div>
          <div className="text-text-primary font-semibold">
            {teamName || '\u2014'}
          </div>
        </div>
        <div>
          <div className="text-text-dim text-xs mb-1">Track</div>
          <div className="text-text-primary font-semibold text-sm">
            {track || '\u2014'}
          </div>
        </div>
        <div>
          <div className="text-text-dim text-xs mb-1">State</div>
          <div className="flex items-center gap-2">
            <StateIndicator state={demoState} />
            <span className="neon-text font-semibold uppercase text-sm">
              {theme.label}
            </span>
          </div>
        </div>
        <div>
          <div className="text-text-dim text-xs mb-1">Elapsed</div>
          <div className="text-text-primary font-semibold text-xl font-mono">
            {demoState === 'capturing' ? formatElapsed(elapsed) : '00:00'}
          </div>
        </div>
      </div>
    </div>
  );
}
