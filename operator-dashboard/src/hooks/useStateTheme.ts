import { useEffect } from "react";
import { useOperatorStore } from "../store/operatorStore";

const STATE_THEMES = {
  idle: {
    accent: "#5588aa",
    accentRgb: "85, 136, 170",
    glow: "rgba(85, 136, 170, 0.15)",
    border: "rgba(85, 136, 170, 0.25)",
    pulseSpeed: 4,
    label: "STANDBY",
  },
  capturing: {
    accent: "#00ff88",
    accentRgb: "0, 255, 136",
    glow: "rgba(0, 255, 136, 0.2)",
    border: "rgba(0, 255, 136, 0.35)",
    pulseSpeed: 1.5,
    label: "CAPTURING",
  },
  paused: {
    accent: "#ffaa00",
    accentRgb: "255, 170, 0",
    glow: "rgba(255, 170, 0, 0.15)",
    border: "rgba(255, 170, 0, 0.25)",
    pulseSpeed: 3,
    label: "PAUSED",
  },
  stopped: {
    accent: "#6688ff",
    accentRgb: "102, 136, 255",
    glow: "rgba(102, 136, 255, 0.15)",
    border: "rgba(102, 136, 255, 0.25)",
    pulseSpeed: 2,
    label: "JUDGING",
  },
} as const;

export function useStateTheme() {
  const demoState = useOperatorStore((s) => s.demoState);

  useEffect(() => {
    const theme = STATE_THEMES[demoState];
    const root = document.documentElement;
    root.style.setProperty("--accent", theme.accent);
    root.style.setProperty("--accent-rgb", theme.accentRgb);
    root.style.setProperty("--glow", theme.glow);
    root.style.setProperty("--border-accent", theme.border);
    root.style.setProperty("--pulse-speed", `${theme.pulseSpeed}s`);
  }, [demoState]);

  return STATE_THEMES[demoState];
}
