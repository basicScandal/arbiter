import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { DefenseStrip } from "../DefenseStrip";
import { useOperatorStore } from "../../store/operatorStore";
import type { EventEntry } from "../../store/operatorStore";

describe("DefenseStrip", () => {
  beforeEach(() => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 0, clean: 0 },
      events: [],
    });
  });

  it("renders DEFENSE label", () => {
    render(<DefenseStrip />);
    expect(screen.getByText("DEFENSE")).toBeInTheDocument();
  });

  it("shows blocked and clean labels", () => {
    render(<DefenseStrip />);
    expect(screen.getByText("blocked")).toBeInTheDocument();
    expect(screen.getByText("clean")).toBeInTheDocument();
  });

  it("shows attacks count", () => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 7, clean: 0 },
    });
    render(<DefenseStrip />);
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("shows clean count", () => {
    useOperatorStore.setState({
      counters: { frames: 0, transcripts: 0, attacks: 0, clean: 23 },
    });
    render(<DefenseStrip />);
    expect(screen.getByText("23")).toBeInTheDocument();
  });

  it("shows last roast text when available", () => {
    const events: EventEntry[] = [
      {
        id: 0,
        event_type: "roast_generated",
        timestamp: 1700000000,
        data: { text: "Nice try with that prompt injection" },
      },
    ];
    useOperatorStore.setState({ events });
    render(<DefenseStrip />);
    expect(screen.getByText(/Nice try with that prompt injection/)).toBeInTheDocument();
  });

  it("does not show roast text when no roast events", () => {
    const events: EventEntry[] = [
      { id: 0, event_type: "key_frame_detected", timestamp: 1700000000 },
    ];
    useOperatorStore.setState({ events });
    render(<DefenseStrip />);
    // No italic roast text should be present
    const italicElements = document.querySelectorAll(".italic");
    expect(italicElements).toHaveLength(0);
  });
});
