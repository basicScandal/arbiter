import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useArbiterSocket } from "../useArbiterSocket";
import { useDisplayStore } from "../../store/displayStore";

// ---------------------------------------------------------------------------
// Mock WebSocket
// ---------------------------------------------------------------------------

interface MockWebSocketInstance {
  url: string;
  onopen: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  close: ReturnType<typeof vi.fn>;
  send: ReturnType<typeof vi.fn>;
  readyState: number;
}

const mockWsInstances: MockWebSocketInstance[] = [];

class MockWebSocket {
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn(() => {
    this.readyState = 3; // CLOSED
  });
  send = vi.fn();
  readyState = 0; // CONNECTING

  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  constructor(url: string) {
    this.url = url;
    mockWsInstances.push(this as unknown as MockWebSocketInstance);
  }
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.useFakeTimers();
  mockWsInstances.length = 0;

  // Replace global WebSocket with our mock
  vi.stubGlobal("WebSocket", MockWebSocket);

  // Reset location to http so ws: protocol is used
  Object.defineProperty(window, "location", {
    value: {
      protocol: "http:",
      host: "localhost:8080",
    },
    writable: true,
  });

  // Reset store
  useDisplayStore.setState({
    connected: false,
    activeScreen: "idle",
    teamName: "",
    commentaryText: "",
    commentarySentences: [],
    isQuestion: false,
    scoreTeamName: "",
    criteria: [],
    scoreTotal: null,
    rankings: [],
    narrative: "",
    injectionAlert: null,
    intermissionData: null,
    thinkingTeam: null,
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useArbiterSocket", () => {
  it("creates WebSocket with correct URL on mount", () => {
    renderHook(() => useArbiterSocket());

    expect(mockWsInstances).toHaveLength(1);
    expect(mockWsInstances[0].url).toBe("ws://localhost:8080/ws/display");
  });

  it("uses wss: protocol when page is https", () => {
    Object.defineProperty(window, "location", {
      value: { protocol: "https:", host: "example.com" },
      writable: true,
    });

    renderHook(() => useArbiterSocket());
    expect(mockWsInstances[0].url).toBe("wss://example.com/ws/display");
  });

  it("sets connected=true on WebSocket open", () => {
    renderHook(() => useArbiterSocket());

    const ws = mockWsInstances[0];
    expect(useDisplayStore.getState().connected).toBe(false);

    ws.onopen?.();
    expect(useDisplayStore.getState().connected).toBe(true);
  });

  it("dispatches parsed messages on message event", () => {
    renderHook(() => useArbiterSocket());

    const ws = mockWsInstances[0];
    ws.onopen?.();

    ws.onmessage?.({
      data: JSON.stringify({
        type: "commentary",
        text: "Hello from WS",
        team_name: "Socket Team",
        sentence_index: 0,
      }),
    });

    const state = useDisplayStore.getState();
    expect(state.activeScreen).toBe("commentary");
    expect(state.teamName).toBe("Socket Team");
    expect(state.commentaryText).toBe("Hello from WS");
  });

  it("sets connected=false on WebSocket close", () => {
    renderHook(() => useArbiterSocket());

    const ws = mockWsInstances[0];
    ws.onopen?.();
    expect(useDisplayStore.getState().connected).toBe(true);

    ws.onclose?.();
    expect(useDisplayStore.getState().connected).toBe(false);
  });

  it("reconnects after close with initial backoff of 1000ms", () => {
    renderHook(() => useArbiterSocket());

    expect(mockWsInstances).toHaveLength(1);
    const ws = mockWsInstances[0];
    ws.onopen?.();
    ws.onclose?.();

    expect(mockWsInstances).toHaveLength(1); // no reconnect yet

    vi.advanceTimersByTime(1000);
    expect(mockWsInstances).toHaveLength(2); // reconnected
  });

  it("uses exponential backoff on repeated disconnections", () => {
    renderHook(() => useArbiterSocket());

    // First disconnect (no open) — backoff stays at 1000, schedules reconnect in 1000ms
    // Inside that callback, backoff doubles to 2000, then ws2 is created
    const ws1 = mockWsInstances[0];
    ws1.onclose?.();
    vi.advanceTimersByTime(1000); // ws2 created, backoff is now 2000

    expect(mockWsInstances).toHaveLength(2);

    // Second disconnect (no open) — backoff is 2000, schedules reconnect in 2000ms
    // Inside that callback, backoff doubles to 4000, then ws3 is created
    const ws2 = mockWsInstances[1];
    ws2.onclose?.();

    // Should not reconnect before 2000ms
    vi.advanceTimersByTime(1999);
    expect(mockWsInstances).toHaveLength(2);

    // Should reconnect at 2000ms
    vi.advanceTimersByTime(1);
    expect(mockWsInstances).toHaveLength(3);
  });

  it("caps backoff at MAX_BACKOFF_MS (10000ms)", () => {
    renderHook(() => useArbiterSocket());

    // Drive backoff up by closing without ever opening (no reset).
    // Backoff sequence when closing without opening:
    //   close at backoff=1000 → wait 1000ms → backoff becomes 2000 → connect
    //   close at backoff=2000 → wait 2000ms → backoff becomes 4000 → connect
    //   close at backoff=4000 → wait 4000ms → backoff becomes 8000 → connect
    //   close at backoff=8000 → wait 8000ms → backoff becomes 10000 (capped) → connect
    const delays = [1000, 2000, 4000, 8000];
    for (const delay of delays) {
      const ws = mockWsInstances[mockWsInstances.length - 1];
      ws.onclose?.();
      vi.advanceTimersByTime(delay);
    }

    // Now backoff is capped at 10000.
    // Next close should schedule reconnect in exactly 10000ms.
    const lastWs = mockWsInstances[mockWsInstances.length - 1];
    lastWs.onclose?.();

    const countBefore = mockWsInstances.length;

    // Should NOT reconnect before 10000ms
    vi.advanceTimersByTime(9999);
    expect(mockWsInstances).toHaveLength(countBefore);

    // Should reconnect at exactly 10000ms
    vi.advanceTimersByTime(1);
    expect(mockWsInstances).toHaveLength(countBefore + 1);
  });

  it("closes WebSocket and does not reconnect on unmount", () => {
    const { unmount } = renderHook(() => useArbiterSocket());

    const ws = mockWsInstances[0];
    ws.onopen?.();

    unmount();

    expect(ws.close).toHaveBeenCalledTimes(1);

    // Fire close after unmount — should NOT trigger reconnect
    ws.onclose?.();
    vi.advanceTimersByTime(10_000);
    expect(mockWsInstances).toHaveLength(1);
  });

  it("ignores malformed JSON messages without crashing", () => {
    renderHook(() => useArbiterSocket());

    const ws = mockWsInstances[0];
    ws.onopen?.();

    // Should not throw
    expect(() => {
      ws.onmessage?.({ data: "this is not json {{{{" });
    }).not.toThrow();

    // Store state should remain unchanged
    expect(useDisplayStore.getState().activeScreen).toBe("idle");
  });

  it("resets backoff to 1000 on successful open", () => {
    renderHook(() => useArbiterSocket());

    // Force backoff up by disconnecting without opening
    const ws1 = mockWsInstances[0];
    ws1.onclose?.();
    vi.advanceTimersByTime(1000);

    const ws2 = mockWsInstances[1];
    ws2.onclose?.();
    vi.advanceTimersByTime(2000); // backoff doubled to 2000

    // Now open successfully — backoff should reset
    const ws3 = mockWsInstances[2];
    ws3.onopen?.(); // resets backoff to 1000

    ws3.onclose?.();
    // Next reconnect should happen at 1000ms, not 4000ms
    vi.advanceTimersByTime(999);
    expect(mockWsInstances).toHaveLength(3);

    vi.advanceTimersByTime(1);
    expect(mockWsInstances).toHaveLength(4);
  });
});
