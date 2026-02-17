import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusPanel } from "../StatusPanel";
import { useOperatorStore } from "../../store/operatorStore";

describe("StatusPanel", () => {
  beforeEach(() => {
    useOperatorStore.setState({
      demoState: "idle",
      teamName: "",
      track: "",
      startedAt: null,
    });
  });

  it("shows dash when no team name", () => {
    render(<StatusPanel />);
    const dashes = screen.getAllByText("\u2014");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it("shows dash when no track", () => {
    render(<StatusPanel />);
    const dashes = screen.getAllByText("\u2014");
    expect(dashes.length).toBeGreaterThanOrEqual(2);
  });

  it("shows team name from store", () => {
    useOperatorStore.setState({ teamName: "AlphaSquad" });
    render(<StatusPanel />);
    expect(screen.getByText("AlphaSquad")).toBeInTheDocument();
  });

  it("shows track from store", () => {
    useOperatorStore.setState({ track: "ROGUE::AGENT" });
    render(<StatusPanel />);
    expect(screen.getByText("ROGUE::AGENT")).toBeInTheDocument();
  });

  it("shows 00:00 elapsed when not capturing", () => {
    render(<StatusPanel />);
    expect(screen.getByText("00:00")).toBeInTheDocument();
  });

  it("shows 00:00 when idle even with startedAt", () => {
    useOperatorStore.setState({ demoState: "idle", startedAt: 1700000000 });
    render(<StatusPanel />);
    expect(screen.getByText("00:00")).toBeInTheDocument();
  });

  it("renders STATUS heading", () => {
    render(<StatusPanel />);
    expect(screen.getByText("STATUS")).toBeInTheDocument();
  });

  it("displays theme label for current state", () => {
    useOperatorStore.setState({ demoState: "capturing" });
    render(<StatusPanel />);
    expect(screen.getByText("CAPTURING")).toBeInTheDocument();
  });

  it("renders StateIndicator matching demoState", () => {
    useOperatorStore.setState({ demoState: "paused" });
    render(<StatusPanel />);
    const indicator = document.querySelector('div[title="State: paused"]');
    expect(indicator).toBeInTheDocument();
  });
});
