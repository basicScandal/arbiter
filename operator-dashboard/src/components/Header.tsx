import { useState } from "react";
import { useOperatorStore } from "../store/operatorStore";
import { ConnectionDot } from "./ConnectionDot";
import { StateIndicator } from "./StateIndicator";
import { useStateTheme } from "../hooks/useStateTheme";

interface HeaderProps {
  muted: boolean;
  onToggleMute: () => void;
}

async function downloadExport() {
  const res = await fetch("/api/export?include_events=true&include_audit=true");
  if (!res.ok) throw new Error(`Export failed: ${res.status}`);
  const data = await res.json();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  a.download = `arbiter-export-${ts}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

export function Header({ muted, onToggleMute }: HeaderProps) {
  const demoState = useOperatorStore((s) => s.demoState);
  const theme = useStateTheme();
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      await downloadExport();
    } catch (e) {
      console.error("Export failed:", e);
    } finally {
      setExporting(false);
    }
  };

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
        <button
          onClick={handleExport}
          disabled={exporting}
          className="text-text-dim hover:text-text-primary transition-colors text-sm disabled:opacity-40"
          title="Export all event data as JSON"
          aria-label="Export event data"
        >
          {exporting ? "\u23F3" : "\uD83D\uDCE5"}
        </button>
        <button
          onClick={onToggleMute}
          className="text-text-dim hover:text-text-primary transition-colors text-sm"
          title={muted ? "Unmute sounds" : "Mute sounds"}
          aria-label={muted ? "Unmute audio" : "Mute audio"}
          aria-pressed={!muted}
        >
          {muted ? "\uD83D\uDD07" : "\uD83D\uDD0A"}
        </button>
      </div>
    </header>
  );
}
