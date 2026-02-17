import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { HealthPanel } from "../HealthPanel";
import { useOperatorStore } from "../../store/operatorStore";

describe("HealthPanel", () => {
  beforeEach(() => {
    useOperatorStore.setState({ health: {} });
  });

  it("renders SYSTEM HEALTH heading", () => {
    render(<HealthPanel />);
    expect(screen.getByText("SYSTEM HEALTH")).toBeInTheDocument();
  });

  it("shows nominal message when no services tracked", () => {
    render(<HealthPanel />);
    expect(screen.getByText("All systems nominal")).toBeInTheDocument();
  });

  it("renders healthy service as ONLINE", () => {
    useOperatorStore.setState({ health: { cartesia_tts: true } });
    render(<HealthPanel />);
    expect(screen.getByText("ONLINE")).toBeInTheDocument();
    expect(screen.getByText("cartesia tts")).toBeInTheDocument();
  });

  it("renders unhealthy service as DEGRADED", () => {
    useOperatorStore.setState({ health: { cartesia_tts: false } });
    render(<HealthPanel />);
    expect(screen.getByText("DEGRADED")).toBeInTheDocument();
  });

  it("renders multiple services", () => {
    useOperatorStore.setState({ health: { cartesia_tts: true, gemini_live: false } });
    render(<HealthPanel />);
    expect(screen.getByText("ONLINE")).toBeInTheDocument();
    expect(screen.getByText("DEGRADED")).toBeInTheDocument();
  });
});
