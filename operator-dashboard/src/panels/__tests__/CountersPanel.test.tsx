import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { CountersPanel } from "../CountersPanel";
import { useOperatorStore } from "../../store/operatorStore";

describe("CountersPanel", () => {
  beforeEach(() => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 0, clean: 0 },
    });
  });

  it("renders COUNTERS heading", () => {
    render(<CountersPanel />);
    expect(screen.getByText("COUNTERS")).toBeInTheDocument();
  });

  it("renders all 4 counter labels", () => {
    render(<CountersPanel />);
    expect(screen.getByText("Frames")).toBeInTheDocument();
    expect(screen.getByText("Transcripts")).toBeInTheDocument();
    expect(screen.getByText("Attacks")).toBeInTheDocument();
    expect(screen.getByText("Clean")).toBeInTheDocument();
  });

  it("renders zero values", () => {
    render(<CountersPanel />);
    const zeros = screen.getAllByText("0");
    expect(zeros).toHaveLength(4);
  });

  it("renders updated counter values", () => {
    useOperatorStore.setState({
      counters: { frames: 42, transcripts: 15, attacks: 3, clean: 12 },
    });
    render(<CountersPanel />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("renders progress bars", () => {
    useOperatorStore.setState({
      counters: { frames: 100, transcripts: 50, attacks: 25, clean: 75 },
    });
    render(<CountersPanel />);
    // Progress bars are divs with transition-all class and width style
    const bars = document.querySelectorAll("[style]");
    expect(bars.length).toBeGreaterThanOrEqual(4);
  });

  it("scales progress bars relative to max value", () => {
    useOperatorStore.setState({
      counters: { frames: 100, transcripts: 50, attacks: 0, clean: 0 },
    });
    render(<CountersPanel />);
    // Max is 100 (frames). Frames bar should be 100%, transcripts should be 50%
    const bars = document.querySelectorAll(".transition-all.duration-300");
    const barStyles = Array.from(bars).map(
      (b) => (b as HTMLElement).style.width
    );
    expect(barStyles).toContain("100%");
    expect(barStyles).toContain("50%");
  });

  it("uses minimum max of 1 to avoid division by zero", () => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 0, clean: 0 },
    });
    render(<CountersPanel />);
    // All bars should be 0% width, not NaN
    const bars = document.querySelectorAll(".transition-all.duration-300");
    Array.from(bars).forEach((b) => {
      expect((b as HTMLElement).style.width).toBe("0%");
    });
  });
});
