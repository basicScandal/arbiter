import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { VitalsPanel } from "../VitalsPanel";
import { useOperatorStore } from "../../store/operatorStore";

describe("VitalsPanel", () => {
  beforeEach(() => {
    useOperatorStore.setState({
      demoState: "idle",
      teamName: "",
      track: "",
      startedAt: null,
      counters: { frames: 0, transcripts: 0, attacks: 0, clean: 0 },
    });
  });

  it("renders VITALS heading", () => {
    render(<VitalsPanel />);
    expect(screen.getByText("VITALS")).toBeInTheDocument();
  });

  // Status section
  it("shows dash when no team name", () => {
    render(<VitalsPanel />);
    // Team and Track both show em-dash when empty, formatted as "— / —"
    const text = screen.getByText(/\u2014 \/ \u2014/);
    expect(text).toBeInTheDocument();
  });

  it("shows team name and track", () => {
    useOperatorStore.setState({ teamName: "AlphaSquad", track: "ROGUE::AGENT" });
    render(<VitalsPanel />);
    expect(screen.getByText("AlphaSquad / ROGUE::AGENT")).toBeInTheDocument();
  });

  it("displays theme label for current state", () => {
    useOperatorStore.setState({ demoState: "capturing" });
    render(<VitalsPanel />);
    expect(screen.getByText("CAPTURING")).toBeInTheDocument();
  });

  it("renders StateIndicator", () => {
    useOperatorStore.setState({ demoState: "paused" });
    render(<VitalsPanel />);
    const indicator = document.querySelector('div[title="State: paused"]');
    expect(indicator).toBeInTheDocument();
  });

  it("shows 00:00 elapsed when not capturing", () => {
    render(<VitalsPanel />);
    expect(screen.getByText("00:00")).toBeInTheDocument();
  });

  // Counters section
  it("renders counter labels", () => {
    render(<VitalsPanel />);
    expect(screen.getByText("Frames")).toBeInTheDocument();
    expect(screen.getByText("Audio")).toBeInTheDocument();
    expect(screen.getByText("Threats")).toBeInTheDocument();
  });

  it("renders counter values", () => {
    useOperatorStore.setState({
      counters: { frames: 42, transcripts: 15, attacks: 3, clean: 12 },
    });
    render(<VitalsPanel />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  // Shield section
  it("shows Shield label", () => {
    render(<VitalsPanel />);
    expect(screen.getByText("Shield")).toBeInTheDocument();
  });

  it("shows 100% shield when zero total", () => {
    render(<VitalsPanel />);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("calculates shield percentage correctly", () => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 3, clean: 7 },
    });
    render(<VitalsPanel />);
    expect(screen.getByText("70%")).toBeInTheDocument();
  });

  it("shows 0% shield when all attacks", () => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 10, clean: 0 },
    });
    render(<VitalsPanel />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });
});
