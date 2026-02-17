import { useOperatorStore } from "../store/operatorStore";

export function CountersPanel() {
  const counters = useOperatorStore((s) => s.counters);

  const maxValue = Math.max(
    counters.frames,
    counters.transcripts,
    counters.attacks,
    counters.clean,
    1,
  );

  const renderCounter = (label: string, value: number, color: string) => {
    const widthPercent = (value / maxValue) * 100;
    return (
      <div className="mb-3">
        <div className="flex justify-between items-baseline mb-1">
          <span className="text-arbiter-muted text-sm">{label}</span>
          <span className="text-arbiter-text font-bold text-lg">{value}</span>
        </div>
        <div className="w-full bg-arbiter-bg rounded-full h-2 overflow-hidden">
          <div
            className={`h-full ${color} transition-all duration-300`}
            style={{ width: `${widthPercent}%` }}
          />
        </div>
      </div>
    );
  };

  return (
    <div className="bg-arbiter-surface border border-arbiter-accent-dim rounded-lg p-4">
      <h2 className="text-lg font-bold text-arbiter-accent mb-3">COUNTERS</h2>
      {renderCounter('Frames', counters.frames, 'bg-arbiter-cyan')}
      {renderCounter('Transcripts', counters.transcripts, 'bg-arbiter-green')}
      {renderCounter('Attacks', counters.attacks, 'bg-arbiter-red')}
      {renderCounter('Clean', counters.clean, 'bg-arbiter-gold')}
    </div>
  );
}
