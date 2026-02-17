import { useOperatorStore } from "../store/operatorStore";

export function DefensePanel() {
  const counters = useOperatorStore((s) => s.counters);

  const total = counters.attacks + counters.clean;
  const shieldPercent = total > 0 ? Math.round((counters.clean / total) * 100) : 0;

  return (
    <div className="bg-arbiter-surface border border-arbiter-accent-dim rounded-lg p-4">
      <h2 className="text-lg font-bold text-arbiter-accent mb-3">DEFENSE</h2>
      <div className="space-y-3">
        <div className="flex justify-between items-baseline">
          <span className="text-arbiter-muted text-sm">Attacks</span>
          <span className="text-arbiter-red font-bold text-lg">
            {counters.attacks}
          </span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className="text-arbiter-muted text-sm">Clean</span>
          <span className="text-arbiter-green font-bold text-lg">
            {counters.clean}
          </span>
        </div>
        <div className="pt-2 border-t border-arbiter-accent-dim">
          <div className="flex justify-between items-baseline mb-2">
            <span className="text-arbiter-muted text-sm">Shield</span>
            <span className="text-arbiter-gold font-bold text-2xl">
              {shieldPercent}%
            </span>
          </div>
          <div className="w-full bg-arbiter-bg rounded-full h-3 overflow-hidden">
            <div
              className="h-full bg-arbiter-gold transition-all duration-500"
              style={{ width: `${shieldPercent}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
