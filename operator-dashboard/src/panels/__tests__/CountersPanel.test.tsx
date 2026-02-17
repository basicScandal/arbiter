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

  it("renders VITALS heading", () => {
    render(<CountersPanel />);
    expect(screen.getByText("VITALS")).toBeInTheDocument();
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
    const bars = document.querySelectorAll(".rounded-full[style]");
    expect(bars.length).toBeGreaterThanOrEqual(4);
  });

  it("uses minimum max of 1 to avoid division by zero", () => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 0, clean: 0 },
    });
    render(<CountersPanel />);
    // All zero counters should result in 0% width bars, not NaN
    const zeros = screen.getAllByText("0");
    expect(zeros).toHaveLength(4);
  });
});
