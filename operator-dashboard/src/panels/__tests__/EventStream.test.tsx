import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { EventStream } from "../EventStream";
import { useOperatorStore } from "../../store/operatorStore";
import type { EventEntry } from "../../store/operatorStore";

describe("EventStream", () => {
  beforeEach(() => {
    useOperatorStore.setState({ events: [] });
  });

  it("shows empty state message when no events", () => {
    render(<EventStream />);
    expect(screen.getByText("Awaiting neural activity...")).toBeInTheDocument();
  });

  it("renders NEURAL FEED heading", () => {
    render(<EventStream />);
    expect(screen.getByText("NEURAL FEED")).toBeInTheDocument();
  });

  it("renders known event types with semantic labels", () => {
    const events: EventEntry[] = [
      { id: 1, event_type: "key_frame_detected", timestamp: 1700000000 },
      { id: 0, event_type: "transcript_received", timestamp: 1699999900 },
    ];
    useOperatorStore.setState({ events });
    render(<EventStream />);
    expect(screen.getByText("Key frame")).toBeInTheDocument();
    expect(screen.getByText("Transcript")).toBeInTheDocument();
  });

  it("renders unknown event types as fallback label", () => {
    const events: EventEntry[] = [
      { id: 0, event_type: "custom_event", timestamp: 1700000000 },
    ];
    useOperatorStore.setState({ events });
    render(<EventStream />);
    expect(screen.getByText("custom_event")).toBeInTheDocument();
  });

  it("renders timestamps", () => {
    const events: EventEntry[] = [
      { id: 0, event_type: "demo_started", timestamp: 1700000000 },
    ];
    useOperatorStore.setState({ events });
    render(<EventStream />);
    const timeElements = document.querySelectorAll(".text-text-dim.shrink-0");
    expect(timeElements.length).toBeGreaterThanOrEqual(1);
  });

  it("does not render detail span when no data", () => {
    const events: EventEntry[] = [
      { id: 0, event_type: "key_frame_detected", timestamp: 1700000000 },
    ];
    useOperatorStore.setState({ events });
    render(<EventStream />);
    const truncateSpans = document.querySelectorAll(".text-text-secondary.truncate");
    expect(truncateSpans).toHaveLength(0);
  });

  it("formats commentary events with text detail", () => {
    const events: EventEntry[] = [
      {
        id: 0,
        event_type: "commentary_delivered",
        timestamp: 1700000000,
        data: { text: "Great presentation by the team" },
      },
    ];
    useOperatorStore.setState({ events });
    render(<EventStream />);
    expect(screen.getByText("Great presentation by the team")).toBeInTheDocument();
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
    render(<EventStream />);
    expect(screen.getByText("visual_overlay (0.92)")).toBeInTheDocument();
  });

  it("renders semantic icons for known events", () => {
    const events: EventEntry[] = [
      { id: 0, event_type: "injection_detected", timestamp: 1700000000, data: { attempt: { injection_type: "test", confidence: 0.5 } } },
    ];
    useOperatorStore.setState({ events });
    render(<EventStream />);
    expect(screen.getByText("INJECTION")).toBeInTheDocument();
  });

  it("applies injection styling to injection events", () => {
    const events: EventEntry[] = [
      { id: 0, event_type: "injection_detected", timestamp: 1700000000, data: { attempt: { injection_type: "test", confidence: 0.5 } } },
    ];
    useOperatorStore.setState({ events });
    render(<EventStream />);
    const injectionRow = document.querySelector(".bg-event-injection\\/5");
    expect(injectionRow).toBeInTheDocument();
  });
});
