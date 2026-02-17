import { useOperatorStore } from "../store/operatorStore";
import { ConnectionDot } from "./ConnectionDot";
import { StateIndicator } from "./StateIndicator";
import { useStateTheme } from "../hooks/useStateTheme";

export function Header() {
  const demoState = useOperatorStore((s) => s.demoState);
  const theme = useStateTheme();

  return (
    <header className="flex items-center justify-between px-6 py-4 glass-panel-elevated">
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold tracking-[0.3em] animate-shimmer">
          ARBITER
        </h1>
        <ConnectionDot />
      </div>
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3">
          <StateIndicator state={demoState} />
          <span className="neon-text font-semibold uppercase tracking-wider text-sm">
            {theme.label}
          </span>
        </div>
      </div>
    </header>
  );
}
