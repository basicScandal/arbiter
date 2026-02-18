import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { NeuralFeed } from "../NeuralFeed";
import { useOperatorStore } from "../../store/operatorStore";
import type { EventEntry } from "../../store/operatorStore";

describe("NeuralFeed", () => {
  beforeEach(() => {
    useOperatorStore.setState({ events: [] });
  });

  it("shows empty state message when no events", () => {
    render(<NeuralFeed />);
    expect(screen.getByText("Awaiting neural activity...")).toBeInTheDocument();
  });

  it("renders NEURAL FEED heading", () => {
    render(<NeuralFeed />);
    expect(screen.getByText("NEURAL FEED")).toBeInTheDocument();
  });

  it("renders known event types with semantic labels", () => {
    const events: EventEntry[] = [
      { id: 1, event_type: "key_frame_detected", timestamp: 1700000000 },
      { id: 0, event_type: "transcript_received", timestamp: 1699999900 },
    ];
    useOperatorStore.setState({ events });
    render(<NeuralFeed />);
    expect(screen.getByText("Key frame")).toBeInTheDocument();
    expect(screen.getByText("Transcript")).toBeInTheDocument();
  });

  it("renders unknown event types as fallback label", () => {
    const events: EventEntry[] = [
      { id: 0, event_type: "custom_event", timestamp: 1700000000 },
    ];
    useOperatorStore.setState({ events });
    render(<NeuralFeed />);
    expect(screen.getByText("custom_event")).toBeInTheDocument();
  });

  it("renders timestamps", () => {
    const events: EventEntry[] = [
      { id: 0, event_type: "demo_started", timestamp: 1700000000 },
    ];
    useOperatorStore.setState({ events });
    render(<NeuralFeed />);
    const timeElements = document.querySelectorAll(".text-text-dim.shrink-0");
    expect(timeElements.length).toBeGreaterThanOrEqual(1);
  });

  it("formats key_frame_detected with static label when no data", () => {
    const events: EventEntry[] = [
      { id: 0, event_type: "key_frame_detected", timestamp: 1700000000 },
    ];
    useOperatorStore.setState({ events });
    render(<NeuralFeed />);
    expect(screen.getByText("Key frame captured")).toBeInTheDocument();
  });

  it("formats commentary events with text detail and left border", () => {
    const events: EventEntry[] = [
      {
        id: 0,
        event_type: "commentary_delivered",
        timestamp: 1700000000,
        data: { text: "Great presentation by the team" },
      },
    ];
    useOperatorStore.setState({ events });
    render(<NeuralFeed />);
    expect(screen.getByText("Great presentation by the team")).toBeInTheDocument();
    const card = document.querySelector(".border-l-2");
    expect(card).toBeInTheDocument();
  });

  it("formats roast events with text detail and left border", () => {
    const events: EventEntry[] = [
      {
        id: 0,
        event_type: "roast_generated",
        timestamp: 1700000000,
        data: { text: "Nice try embedding that prompt overlay" },
      },
    ];
    useOperatorStore.setState({ events });
    render(<NeuralFeed />);
    expect(screen.getByText("Nice try embedding that prompt overlay")).toBeInTheDocument();
    const card = document.querySelector(".border-l-2");
    expect(card).toBeInTheDocument();
  });

  it("formats injection events with type and confidence", () => {
    const events: EventEntry[] = [
      {
        id: 0,
        event_type: "injection_detected",
        timestamp: 1700000000,
        data: { attempt: { injection_type: "visual_overlay", confidence: 0.92 } },
      },
    ];
    useOperatorStore.setState({ events });
    render(<NeuralFeed />);
    expect(screen.getByText("visual_overlay (0.92)")).toBeInTheDocument();
  });

  it("formats scoring_complete events with score", () => {
    const events: EventEntry[] = [
      {
        id: 0,
        event_type: "scoring_complete",
        timestamp: 1700000000,
        data: { scorecard: { team_name: "Alpha", total_score: 8.5 } },
      },
    ];
    useOperatorStore.setState({ events });
    render(<NeuralFeed />);
    expect(screen.getByText("Alpha: 8.5/10")).toBeInTheDocument();
  });

  it("renders semantic icons for known events", () => {
    const events: EventEntry[] = [
      { id: 0, event_type: "injection_detected", timestamp: 1700000000, data: { attempt: { injection_type: "test", confidence: 0.5 } } },
    ];
    useOperatorStore.setState({ events });
    render(<NeuralFeed />);
    expect(screen.getByText("INJECTION")).toBeInTheDocument();
  });

  it("applies injection styling to injection events", () => {
    const events: EventEntry[] = [
      { id: 0, event_type: "injection_detected", timestamp: 1700000000, data: { attempt: { injection_type: "test", confidence: 0.5 } } },
    ];
    useOperatorStore.setState({ events });
    render(<NeuralFeed />);
    const injectionRow = document.querySelector(".bg-event-injection\\/5");
    expect(injectionRow).toBeInTheDocument();
  });
});
