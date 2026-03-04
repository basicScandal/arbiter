import { ConnectionDot } from "./ConnectionDot";
import { useDisplayStore } from "../store/displayStore";

export function Header() {
  const manualOverride = useDisplayStore((s) => s.manualOverride);

  return (
    <header className="flex items-center justify-between px-10 py-5 border-b border-arbiter-accent/20">
      <h1 className="text-3xl font-bold tracking-[0.3em] text-arbiter-accent">
        ARBITER
      </h1>
      <div className="flex items-center gap-4">
        {manualOverride && (
          <span className="text-xs font-bold uppercase tracking-widest text-arbiter-orange animate-pulse">
            Manual Override
          </span>
        )}
        <ConnectionDot />
      </div>
    </header>
  );
}
