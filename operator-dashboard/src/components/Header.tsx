import { useOperatorStore } from "../store/operatorStore";
import { ConnectionDot } from "./ConnectionDot";
import { StateIndicator } from "./StateIndicator";

export function Header() {
  const demoState = useOperatorStore((s) => s.demoState);

  return (
    <header className="flex items-center justify-between px-6 py-4 bg-arbiter-surface border-b border-arbiter-accent-dim">
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold text-arbiter-accent tracking-wider">
          ARBITER OPERATOR
        </h1>
        <ConnectionDot />
      </div>
      <div className="flex items-center gap-3">
        <StateIndicator state={demoState} />
        <span className="text-arbiter-text uppercase font-semibold">
          {demoState}
        </span>
      </div>
    </header>
  );
}
