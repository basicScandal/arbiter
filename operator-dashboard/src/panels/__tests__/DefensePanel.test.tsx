import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { DefensePanel } from "../DefensePanel";
import { useOperatorStore } from "../../store/operatorStore";

describe("DefensePanel", () => {
  beforeEach(() => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 0, clean: 0 },
    });
  });

  it("renders DEFENSE heading", () => {
    render(<DefensePanel />);
    expect(screen.getByText("DEFENSE")).toBeInTheDocument();
  });

  it("shows attacks count", () => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 7, clean: 0 },
    });
    render(<DefensePanel />);
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("shows clean count", () => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 0, clean: 23 },
    });
    render(<DefensePanel />);
    expect(screen.getByText("23")).toBeInTheDocument();
  });

  it("shows Attacks and Clean labels", () => {
    render(<DefensePanel />);
    expect(screen.getByText("Attacks")).toBeInTheDocument();
    expect(screen.getByText("Clean")).toBeInTheDocument();
  });

  it("shows Shield label", () => {
    render(<DefensePanel />);
    expect(screen.getByText("Shield")).toBeInTheDocument();
  });

  it("calculates shield percentage correctly", () => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 3, clean: 7 },
    });
    render(<DefensePanel />);
    // 7 / (3 + 7) * 100 = 70%
    expect(screen.getByText("70%")).toBeInTheDocument();
  });

  it("shows 0% shield when zero total", () => {
    render(<DefensePanel />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("shows 100% shield when all clean", () => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 0, clean: 50 },
    });
    render(<DefensePanel />);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("shows 0% shield when all attacks", () => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 10, clean: 0 },
    });
    render(<DefensePanel />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("rounds shield percentage correctly", () => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 1, clean: 2 },
    });
    render(<DefensePanel />);
    // 2 / 3 * 100 = 66.67, rounded to 67%
    expect(screen.getByText("67%")).toBeInTheDocument();
  });

  it("renders shield progress bar", () => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 2, clean: 8 },
    });
    render(<DefensePanel />);
    const bar = document.querySelector(".bg-arbiter-gold.transition-all");
    expect(bar).toBeInTheDocument();
    expect((bar as HTMLElement).style.width).toBe("80%");
  });
});
