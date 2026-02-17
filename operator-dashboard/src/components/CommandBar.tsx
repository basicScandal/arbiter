import { useState } from "react";
import { useOperatorStore } from "../store/operatorStore";

const TRACKS = [
  "SHADOW::VECTOR",
  "SENTINEL::MESH",
  "ZERO::PROOF",
  "ROGUE::AGENT",
];

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

  return (
    <div className="flex flex-col gap-3 px-6 py-4 bg-arbiter-surface border-t border-arbiter-accent-dim">
      {lastCommandResult && (
        <div className={`text-sm px-3 py-1 rounded ${lastCommandResult.success ? 'text-arbiter-green bg-arbiter-green/10' : 'text-arbiter-red bg-arbiter-red/10'}`}>
          {lastCommandResult.message}
        </div>
      )}
      <div className="flex items-center gap-3">
        <input
          type="text"
          value={teamName}
          onChange={(e) => setTeamName(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && demoState === 'idle') handleStart(); }}
          placeholder="Team Name"
          className="px-3 py-2 bg-arbiter-bg border border-arbiter-muted rounded text-arbiter-text font-mono flex-1"
          disabled={demoState !== 'idle'}
        />
        <select
          value={track}
          onChange={(e) => setTrack(e.target.value)}
          className="px-3 py-2 bg-arbiter-bg border border-arbiter-muted rounded text-arbiter-text font-mono"
          disabled={demoState !== 'idle'}
        >
          {TRACKS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>
      <div className="flex gap-3">
        <button
          onClick={handleStart}
          disabled={demoState !== 'idle' || !teamName.trim()}
          className="px-6 py-3 bg-arbiter-green text-arbiter-bg font-bold rounded hover:opacity-80 disabled:opacity-40 disabled:cursor-not-allowed flex-1"
        >
          START
        </button>
        <button
          onClick={() => sendCommand('stop')}
          disabled={demoState !== 'capturing' && demoState !== 'paused'}
          className="px-6 py-3 bg-arbiter-red text-arbiter-bg font-bold rounded hover:opacity-80 disabled:opacity-40 disabled:cursor-not-allowed flex-1"
        >
          STOP
        </button>
        <button
          onClick={() => sendCommand('pause')}
          disabled={demoState !== 'capturing'}
          className="px-6 py-3 bg-arbiter-yellow text-arbiter-bg font-bold rounded hover:opacity-80 disabled:opacity-40 disabled:cursor-not-allowed flex-1"
        >
          PAUSE
        </button>
        <button
          onClick={() => sendCommand('resume')}
          disabled={demoState !== 'paused'}
          className="px-6 py-3 bg-arbiter-yellow text-arbiter-bg font-bold rounded hover:opacity-80 disabled:opacity-40 disabled:cursor-not-allowed flex-1"
        >
          RESUME
        </button>
        <button
          onClick={() => sendCommand('qa')}
          disabled={demoState !== 'stopped'}
          className="px-6 py-3 bg-arbiter-cyan text-arbiter-bg font-bold rounded hover:opacity-80 disabled:opacity-40 disabled:cursor-not-allowed flex-1"
        >
          QA
        </button>
        <button
          onClick={() => sendCommand('deliberate')}
          disabled={demoState !== 'stopped'}
          className="px-6 py-3 bg-arbiter-purple text-arbiter-bg font-bold rounded hover:opacity-80 disabled:opacity-40 disabled:cursor-not-allowed flex-1"
        >
          DELIBERATE
        </button>
        <button
          onClick={() => sendCommand('reset')}
          disabled={demoState !== 'stopped'}
          className="px-6 py-3 bg-arbiter-muted text-arbiter-bg font-bold rounded hover:opacity-80 disabled:opacity-40 disabled:cursor-not-allowed flex-1"
        >
          RESET
        </button>
      </div>
    </div>
  );
}
