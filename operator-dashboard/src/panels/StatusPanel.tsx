import { useEffect, useState } from "react";
import { useOperatorStore } from "../store/operatorStore";
import { StateIndicator } from "../components/StateIndicator";

export function StatusPanel() {
  const { demoState, teamName, track, startedAt } = useOperatorStore();
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (demoState === 'capturing' && startedAt !== null) {
      const interval = setInterval(() => {
        // startedAt is Unix seconds from Python, Date.now() is ms
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
    <div className="bg-arbiter-surface border border-arbiter-accent-dim rounded-lg p-4">
      <h2 className="text-lg font-bold text-arbiter-accent mb-3">STATUS</h2>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-arbiter-muted text-sm mb-1">Team</div>
          <div className="text-arbiter-text font-semibold">
            {teamName || '—'}
          </div>
        </div>
        <div>
          <div className="text-arbiter-muted text-sm mb-1">Track</div>
          <div className="text-arbiter-text font-semibold">
            {track || '—'}
          </div>
        </div>
        <div>
          <div className="text-arbiter-muted text-sm mb-1">State</div>
          <div className="flex items-center gap-2">
            <StateIndicator state={demoState} />
            <span className="text-arbiter-text font-semibold uppercase">
              {demoState}
            </span>
          </div>
        </div>
        <div>
          <div className="text-arbiter-muted text-sm mb-1">Elapsed</div>
          <div className="text-arbiter-text font-semibold text-xl font-mono">
            {demoState === 'capturing' ? formatElapsed(elapsed) : '00:00'}
          </div>
        </div>
      </div>
    </div>
  );
}
