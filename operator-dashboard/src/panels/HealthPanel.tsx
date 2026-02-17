import { useOperatorStore } from "../store/operatorStore";

export function HealthPanel() {
  const health = useOperatorStore((s) => s.health);
  const entries = Object.entries(health);

  return (
    <div className="glass-panel p-4 animate-border-glow">
      <h2 className="section-label mb-3">SYSTEM HEALTH</h2>
      {entries.length === 0 ? (
        <div className="text-text-dim text-center py-2 text-xs">
          All systems nominal
        </div>
      ) : (
        <div className="space-y-1">
          {entries.map(([service, healthy]) => (
            <div key={service} className="flex justify-between items-center py-1">
              <span className="text-text-dim text-xs uppercase tracking-wider">
                {service.replace(/_/g, " ")}
              </span>
              <span className={`text-xs font-bold ${healthy ? "text-accent-capturing" : "text-event-injection"}`}>
                {healthy ? "ONLINE" : "DEGRADED"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
