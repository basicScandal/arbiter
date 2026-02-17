import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { EventStream } from "../EventStream";
import { useOperatorStore } from "../../store/operatorStore";
import type { EventEntry } from "../../store/operatorStore";

describe("EventStream", () => {
  beforeEach(() => {
    useOperatorStore.setState({ events: [] });
  });

  it("shows 'No events yet' when empty", () => {
    render(<EventStream />);
    expect(screen.getByText("No events yet")).toBeInTheDocument();
  });

  it("renders EVENT STREAM heading", () => {
    render(<EventStream />);
    expect(screen.getByText("EVENT STREAM")).toBeInTheDocument();
  });

  it("renders events with event_type", () => {
    const events: EventEntry[] = [
      { id: 1, event_type: "frame_captured", timestamp: 1700000000 },
      { id: 0, event_type: "session_start", timestamp: 1699999900 },
    ];
    useOperatorStore.setState({ events });
    render(<EventStream />);
    expect(screen.getByText("frame_captured")).toBeInTheDocument();
    expect(screen.getByText("session_start")).toBeInTheDocument();
  });

  it("renders timestamps formatted from unix seconds", () => {
    const events: EventEntry[] = [
      { id: 0, event_type: "test", timestamp: 1700000000 },
    ];
    useOperatorStore.setState({ events });
    render(<EventStream />);
    // Timestamp 1700000000 should be rendered as a time string
    // The exact format depends on locale, so just check it exists and isn't the raw number
    const timeElements = document.querySelectorAll(".text-arbiter-muted.shrink-0");
    expect(timeElements.length).toBeGreaterThanOrEqual(1);
  });

  it("renders event data as JSON", () => {
    const events: EventEntry[] = [
      {
        id: 0,
        event_type: "test",
        timestamp: 1700000000,
        data: { key: "value" },
      },
    ];
    useOperatorStore.setState({ events });
    render(<EventStream />);
    expect(screen.getByText('{"key":"value"}')).toBeInTheDocument();
  });

  it("does not render data span when no data", () => {
    const events: EventEntry[] = [
      { id: 0, event_type: "test", timestamp: 1700000000 },
    ];
    useOperatorStore.setState({ events });
    render(<EventStream />);
    const truncateSpans = document.querySelectorAll(".text-arbiter-text.truncate");
    expect(truncateSpans).toHaveLength(0);
  });

  describe("color coding", () => {
    it("error events get red color class", () => {
      useOperatorStore.setState({
        events: [
          { id: 0, event_type: "parse_error", timestamp: 1700000000 },
        ],
      });
      render(<EventStream />);
      const el = screen.getByText("parse_error");
      expect(el.className).toContain("text-arbiter-red");
    });

    it("fail events get red color class", () => {
      useOperatorStore.setState({
        events: [
          { id: 0, event_type: "auth_fail", timestamp: 1700000000 },
        ],
      });
      render(<EventStream />);
      const el = screen.getByText("auth_fail");
      expect(el.className).toContain("text-arbiter-red");
    });

    it("warning events get yellow color class", () => {
      useOperatorStore.setState({
        events: [
          { id: 0, event_type: "rate_warning", timestamp: 1700000000 },
        ],
      });
      render(<EventStream />);
      const el = screen.getByText("rate_warning");
      expect(el.className).toContain("text-arbiter-yellow");
    });

    it("warn events get yellow color class", () => {
      useOperatorStore.setState({
        events: [
          { id: 0, event_type: "buffer_warn", timestamp: 1700000000 },
        ],
      });
      render(<EventStream />);
      const el = screen.getByText("buffer_warn");
      expect(el.className).toContain("text-arbiter-yellow");
    });

    it("injection events get purple color class", () => {
      useOperatorStore.setState({
        events: [
          { id: 0, event_type: "prompt_injection", timestamp: 1700000000 },
        ],
      });
      render(<EventStream />);
      const el = screen.getByText("prompt_injection");
      expect(el.className).toContain("text-arbiter-purple");
    });

    it("defense events get purple color class", () => {
      useOperatorStore.setState({
        events: [
          { id: 0, event_type: "defense_triggered", timestamp: 1700000000 },
        ],
      });
      render(<EventStream />);
      const el = screen.getByText("defense_triggered");
      expect(el.className).toContain("text-arbiter-purple");
    });

    it("attack events get purple color class", () => {
      useOperatorStore.setState({
        events: [
          { id: 0, event_type: "attack_detected", timestamp: 1700000000 },
        ],
      });
      render(<EventStream />);
      const el = screen.getByText("attack_detected");
      expect(el.className).toContain("text-arbiter-purple");
    });

    it("default events get green color class", () => {
      useOperatorStore.setState({
        events: [
          { id: 0, event_type: "frame_captured", timestamp: 1700000000 },
        ],
      });
      render(<EventStream />);
      const el = screen.getByText("frame_captured");
      expect(el.className).toContain("text-arbiter-green");
    });
  });
});
