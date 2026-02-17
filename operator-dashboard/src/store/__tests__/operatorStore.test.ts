import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { useOperatorStore } from "../operatorStore";
import type { ServerMessage } from "../../types/protocol";

describe("operatorStore", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useOperatorStore.setState({
      connected: false,
      demoState: "idle",
      teamName: "",
      track: "",
      startedAt: null,
      counters: { frames: 0, transcripts: 0, attacks: 0, clean: 0 },
      events: [],
      lastCommandResult: null,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe("initial state", () => {
    it("has correct defaults", () => {
      const state = useOperatorStore.getState();
      expect(state.connected).toBe(false);
      expect(state.demoState).toBe("idle");
      expect(state.teamName).toBe("");
      expect(state.track).toBe("");
      expect(state.startedAt).toBeNull();
      expect(state.counters).toEqual({
        frames: 0,
        transcripts: 0,
        attacks: 0,
        clean: 0,
      });
      expect(state.events).toEqual([]);
      expect(state.lastCommandResult).toBeNull();
    });

    it("has sendCommand as a no-op function", () => {
      const state = useOperatorStore.getState();
      expect(typeof state.sendCommand).toBe("function");
      // Should not throw
      state.sendCommand("test");
    });
  });

  describe("setConnected", () => {
    it("sets connected to true", () => {
      useOperatorStore.getState().setConnected(true);
      expect(useOperatorStore.getState().connected).toBe(true);
    });

    it("sets connected to false", () => {
      useOperatorStore.getState().setConnected(true);
      useOperatorStore.getState().setConnected(false);
      expect(useOperatorStore.getState().connected).toBe(false);
    });
  });

  describe("setSendCommand", () => {
    it("stores the provided function", () => {
      const mockFn = vi.fn();
      useOperatorStore.getState().setSendCommand(mockFn);
      useOperatorStore.getState().sendCommand("test_action", { key: "val" });
      expect(mockFn).toHaveBeenCalledWith("test_action", { key: "val" });
    });
  });

  describe("dispatch - state message", () => {
    it("sets demoState, teamName, track, and startedAt", () => {
      const msg: ServerMessage = {
        type: "state",
        state: "capturing",
        team_name: "Alpha Team",
        track: "ROGUE::AGENT",
        started_at: 1700000000,
      };
      useOperatorStore.getState().dispatch(msg);
      const state = useOperatorStore.getState();
      expect(state.demoState).toBe("capturing");
      expect(state.teamName).toBe("Alpha Team");
      expect(state.track).toBe("ROGUE::AGENT");
      expect(state.startedAt).toBe(1700000000);
    });

    it("handles null started_at", () => {
      const msg: ServerMessage = {
        type: "state",
        state: "idle",
        team_name: "",
        track: "",
        started_at: null,
      };
      useOperatorStore.getState().dispatch(msg);
      expect(useOperatorStore.getState().startedAt).toBeNull();
    });

    it("updates to paused state", () => {
      const msg: ServerMessage = {
        type: "state",
        state: "paused",
        team_name: "Bravo",
        track: "SHADOW::VECTOR",
        started_at: 1700000100,
      };
      useOperatorStore.getState().dispatch(msg);
      expect(useOperatorStore.getState().demoState).toBe("paused");
    });

    it("updates to stopped state", () => {
      const msg: ServerMessage = {
        type: "state",
        state: "stopped",
        team_name: "Charlie",
        track: "ZERO::PROOF",
        started_at: 1700000200,
      };
      useOperatorStore.getState().dispatch(msg);
      expect(useOperatorStore.getState().demoState).toBe("stopped");
    });
  });

  describe("dispatch - event message", () => {
    it("prepends event to events array", () => {
      const msg: ServerMessage = {
        type: "event",
        event_type: "frame_captured",
        timestamp: 1700000000,
        data: { source: "cam1" },
      };
      useOperatorStore.getState().dispatch(msg);
      const events = useOperatorStore.getState().events;
      expect(events).toHaveLength(1);
      expect(events[0].event_type).toBe("frame_captured");
      expect(events[0].timestamp).toBe(1700000000);
      expect(events[0].data).toEqual({ source: "cam1" });
    });

    it("assigns incrementing ids", () => {
      useOperatorStore.getState().dispatch({
        type: "event",
        event_type: "event_a",
        timestamp: 1700000000,
      });
      useOperatorStore.getState().dispatch({
        type: "event",
        event_type: "event_b",
        timestamp: 1700000001,
      });
      const events = useOperatorStore.getState().events;
      // Newest first
      expect(events[0].event_type).toBe("event_b");
      expect(events[1].event_type).toBe("event_a");
      // IDs should be different (incrementing)
      expect(events[0].id).toBeGreaterThan(events[1].id);
    });

    it("maintains newest-first ordering", () => {
      for (let i = 0; i < 5; i++) {
        useOperatorStore.getState().dispatch({
          type: "event",
          event_type: `event_${i}`,
          timestamp: 1700000000 + i,
        });
      }
      const events = useOperatorStore.getState().events;
      expect(events[0].event_type).toBe("event_4");
      expect(events[4].event_type).toBe("event_0");
    });

    it("caps events at 200", () => {
      for (let i = 0; i < 210; i++) {
        useOperatorStore.getState().dispatch({
          type: "event",
          event_type: `event_${i}`,
          timestamp: 1700000000 + i,
        });
      }
      const events = useOperatorStore.getState().events;
      expect(events).toHaveLength(200);
      // Newest event should be the last one dispatched
      expect(events[0].event_type).toBe("event_209");
    });

    it("handles events without data field", () => {
      useOperatorStore.getState().dispatch({
        type: "event",
        event_type: "simple_event",
        timestamp: 1700000000,
      });
      const events = useOperatorStore.getState().events;
      expect(events[0].data).toBeUndefined();
    });
  });

  describe("dispatch - counters message", () => {
    it("updates all 4 counter fields", () => {
      const msg: ServerMessage = {
        type: "counters",
        frames: 42,
        transcripts: 15,
        attacks: 3,
        clean: 12,
      };
      useOperatorStore.getState().dispatch(msg);
      expect(useOperatorStore.getState().counters).toEqual({
        frames: 42,
        transcripts: 15,
        attacks: 3,
        clean: 12,
      });
    });

    it("overwrites previous counter values", () => {
      useOperatorStore.getState().dispatch({
        type: "counters",
        frames: 10,
        transcripts: 5,
        attacks: 1,
        clean: 4,
      });
      useOperatorStore.getState().dispatch({
        type: "counters",
        frames: 20,
        transcripts: 10,
        attacks: 2,
        clean: 8,
      });
      expect(useOperatorStore.getState().counters.frames).toBe(20);
      expect(useOperatorStore.getState().counters.transcripts).toBe(10);
    });
  });

  describe("dispatch - command_result message", () => {
    it("sets lastCommandResult", () => {
      const msg: ServerMessage = {
        type: "command_result",
        success: true,
        message: "Demo started",
      };
      useOperatorStore.getState().dispatch(msg);
      expect(useOperatorStore.getState().lastCommandResult).toEqual({
        success: true,
        message: "Demo started",
      });
    });

    it("stores failure results", () => {
      useOperatorStore.getState().dispatch({
        type: "command_result",
        success: false,
        message: "Failed to start",
      });
      expect(useOperatorStore.getState().lastCommandResult).toEqual({
        success: false,
        message: "Failed to start",
      });
    });

    it("auto-clears after 3 seconds", () => {
      useOperatorStore.getState().dispatch({
        type: "command_result",
        success: true,
        message: "OK",
      });
      expect(useOperatorStore.getState().lastCommandResult).not.toBeNull();
      vi.advanceTimersByTime(3000);
      expect(useOperatorStore.getState().lastCommandResult).toBeNull();
    });

    it("does not clear before 3 seconds", () => {
      useOperatorStore.getState().dispatch({
        type: "command_result",
        success: true,
        message: "OK",
      });
      vi.advanceTimersByTime(2999);
      expect(useOperatorStore.getState().lastCommandResult).not.toBeNull();
    });
  });
});
