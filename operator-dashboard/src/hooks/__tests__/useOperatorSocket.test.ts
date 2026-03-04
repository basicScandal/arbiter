import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useOperatorSocket } from "../useOperatorSocket";
import { useOperatorStore } from "../../store/operatorStore";

// Mock WebSocket
class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;

  readyState = MockWebSocket.OPEN;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  sent: string[] = [];

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
  }
}

let lastCreatedWs: MockWebSocket;

vi.stubGlobal("WebSocket", class extends MockWebSocket {
  constructor() {
    super();
    lastCreatedWs = this;
  }
});

describe("useOperatorSocket", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useOperatorStore.setState({
      connected: false,
      connectionState: "connecting",
      demoState: "idle",
      teamName: "",
      track: "",
      startedAt: null,
      counters: { frames: 0, transcripts: 0, attacks: 0, clean: 0 },
      events: [],
      lastCommandResult: null,
      health: {},
      lastScorecard: null,
      scoringPhase: null,
      demoTimer: null,
      pendingCommand: null,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("sends get_state on connect", () => {
    renderHook(() => useOperatorSocket());

    // Simulate WS open
    lastCreatedWs.onopen?.();

    const sent = lastCreatedWs.sent;
    expect(sent.length).toBeGreaterThanOrEqual(1);
    const parsed = JSON.parse(sent[0]);
    expect(parsed).toEqual({ type: "command", action: "get_state" });
  });

  it("dispatches 'Not connected' error when sendCommand is called while disconnected", () => {
    renderHook(() => useOperatorSocket());

    // Close the WebSocket
    lastCreatedWs.readyState = MockWebSocket.CLOSED;

    // Call sendCommand via the store (which wraps the hook's sendCommand)
    const state = useOperatorStore.getState();
    state.sendCommand("stop");

    const result = useOperatorStore.getState().lastCommandResult;
    expect(result).not.toBeNull();
    expect(result!.success).toBe(false);
    expect(result!.message).toMatch(/not connected/i);
  });
});
