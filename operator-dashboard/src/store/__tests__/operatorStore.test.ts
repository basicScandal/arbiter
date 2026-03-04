import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { useOperatorStore } from "../operatorStore";
import type { ServerMessage } from "../../types/protocol";

describe("operatorStore", () => {
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

    it("resets lastScorecard when demo starts capturing", () => {
      const store = useOperatorStore.getState();

      // Simulate previous demo scorecard
      store.dispatch({
        type: "event",
        event_type: "scoring_complete",
        timestamp: Date.now(),
        data: {
          scorecard: {
            team_name: "Previous Team",
            track: "blue",
            total_score: 8.5,
            criteria: [
              { name: "Innovation", score: 9, weight: 0.5, justification: "Great work" }
            ],
            track_bonus: null,
          },
        },
      });

      expect(useOperatorStore.getState().lastScorecard).not.toBeNull();
      expect(useOperatorStore.getState().lastScorecard?.team_name).toBe("Previous Team");

      // New demo starts
      store.dispatch({
        type: "state",
        state: "capturing",
        team_name: "New Team",
        track: "red",
        started_at: Date.now(),
      });

      // Scorecard should be reset
      expect(useOperatorStore.getState().lastScorecard).toBeNull();
      expect(useOperatorStore.getState().teamName).toBe("New Team");
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

  describe("dispatch - scoring_phase message", () => {
    it("sets scoringPhase to sanitizing", () => {
      useOperatorStore.getState().dispatch({
        type: "scoring_phase",
        phase: "sanitizing",
      });
      expect(useOperatorStore.getState().scoringPhase).toBe("sanitizing");
    });

    it("sets scoringPhase to scoring", () => {
      useOperatorStore.getState().dispatch({
        type: "scoring_phase",
        phase: "scoring",
      });
      expect(useOperatorStore.getState().scoringPhase).toBe("scoring");
    });

    it("sets scoringPhase to revealing", () => {
      useOperatorStore.getState().dispatch({
        type: "scoring_phase",
        phase: "revealing",
      });
      expect(useOperatorStore.getState().scoringPhase).toBe("revealing");
    });

    it("clears scoringPhase with null", () => {
      // First set a phase
      useOperatorStore.getState().dispatch({
        type: "scoring_phase",
        phase: "sanitizing",
      });
      expect(useOperatorStore.getState().scoringPhase).toBe("sanitizing");

      // Then clear it
      useOperatorStore.getState().dispatch({
        type: "scoring_phase",
        phase: null,
      });
      expect(useOperatorStore.getState().scoringPhase).toBeNull();
    });

    it("overrides previous scoringPhase with new phase", () => {
      useOperatorStore.getState().dispatch({
        type: "scoring_phase",
        phase: "sanitizing",
      });
      useOperatorStore.getState().dispatch({
        type: "scoring_phase",
        phase: "scoring",
      });
      useOperatorStore.getState().dispatch({
        type: "scoring_phase",
        phase: "revealing",
      });
      expect(useOperatorStore.getState().scoringPhase).toBe("revealing");
    });
  });

  describe("dispatch - state resets scoringPhase on transitions", () => {
    it("resets lastScorecard to null on idle state", () => {
      // Set a scorecard from a completed demo
      useOperatorStore.getState().dispatch({
        type: "event",
        event_type: "scoring_complete",
        timestamp: Date.now(),
        data: {
          scorecard: {
            team_name: "Old Team",
            track: "ZERO::PROOF",
            total_score: 7.2,
            criteria: [{ name: "Security", score: 7, weight: 0.5, justification: "Solid" }],
            track_bonus: null,
          },
        },
      });
      expect(useOperatorStore.getState().lastScorecard).not.toBeNull();

      useOperatorStore.getState().dispatch({
        type: "state",
        state: "idle",
        team_name: "",
        track: "",
        started_at: null,
      });
      expect(useOperatorStore.getState().lastScorecard).toBeNull();
    });

    it("resets scoringPhase to null on idle state", () => {
      useOperatorStore.getState().dispatch({
        type: "scoring_phase",
        phase: "revealing",
      });
      expect(useOperatorStore.getState().scoringPhase).toBe("revealing");

      useOperatorStore.getState().dispatch({
        type: "state",
        state: "idle",
        team_name: "",
        track: "",
        started_at: null,
      });
      expect(useOperatorStore.getState().scoringPhase).toBeNull();
    });

    it("resets scoringPhase to null on capturing state", () => {
      useOperatorStore.getState().dispatch({
        type: "scoring_phase",
        phase: "sanitizing",
      });
      expect(useOperatorStore.getState().scoringPhase).toBe("sanitizing");

      useOperatorStore.getState().dispatch({
        type: "state",
        state: "capturing",
        team_name: "Team A",
        track: "ROGUE::AGENT",
        started_at: Date.now(),
      });
      expect(useOperatorStore.getState().scoringPhase).toBeNull();
    });

    it("does NOT infer scoringPhase from stopped state — relies on server push", () => {
      useOperatorStore.getState().dispatch({
        type: "state",
        state: "stopped",
        team_name: "Team B",
        track: "ROGUE::AGENT",
        started_at: null,
      });
      // scoringPhase stays null; server will push it explicitly
      expect(useOperatorStore.getState().scoringPhase).toBeNull();
    });
  });

  describe("dispatch - scoring_complete extracts scorecard only", () => {
    it("extracts scorecard from scoring_complete without setting scoringPhase", () => {
      const scorecard = {
        team_name: "TestTeam",
        track: "ROGUE::AGENT",
        total_score: 8.5,
        criteria: [{ name: "Innovation", score: 9, weight: 0.5, justification: "Great" }],
        track_bonus: null,
      };

      useOperatorStore.getState().dispatch({
        type: "event",
        event_type: "scoring_complete",
        timestamp: Date.now(),
        data: { scorecard },
      });

      expect(useOperatorStore.getState().lastScorecard).toEqual(scorecard);
      // scoringPhase NOT set by event — only by scoring_phase message
      expect(useOperatorStore.getState().scoringPhase).toBeNull();
    });

    it("does NOT set scoringPhase from observation_verified event — relies on server push", () => {
      useOperatorStore.getState().dispatch({
        type: "event",
        event_type: "observation_verified",
        timestamp: Date.now(),
      });
      // scoringPhase stays null; server will push it explicitly
      expect(useOperatorStore.getState().scoringPhase).toBeNull();
    });
  });

  describe("dispatch - demoTimer clearing on state transitions", () => {
    it("clears demoTimer on idle state", () => {
      useOperatorStore.getState().dispatch({
        type: "demo_timer",
        level: "warning",
        message: "5:00 elapsed",
        elapsed: 300,
      });
      expect(useOperatorStore.getState().demoTimer).not.toBeNull();

      useOperatorStore.getState().dispatch({
        type: "state",
        state: "idle",
        team_name: "",
        track: "",
        started_at: null,
      });
      expect(useOperatorStore.getState().demoTimer).toBeNull();
    });

    it("clears demoTimer on capturing state", () => {
      useOperatorStore.getState().dispatch({
        type: "demo_timer",
        level: "critical",
        message: "7:00 elapsed",
        elapsed: 420,
      });
      expect(useOperatorStore.getState().demoTimer).not.toBeNull();

      useOperatorStore.getState().dispatch({
        type: "state",
        state: "capturing",
        team_name: "Team A",
        track: "ROGUE::AGENT",
        started_at: Date.now(),
      });
      expect(useOperatorStore.getState().demoTimer).toBeNull();
    });

    it("clears demoTimer on stopped state", () => {
      useOperatorStore.getState().dispatch({
        type: "demo_timer",
        level: "critical",
        message: "8:00 — TIME IS UP",
        elapsed: 480,
      });
      expect(useOperatorStore.getState().demoTimer).not.toBeNull();

      useOperatorStore.getState().dispatch({
        type: "state",
        state: "stopped",
        team_name: "Team A",
        track: "ROGUE::AGENT",
        started_at: 1700000000,
      });
      expect(useOperatorStore.getState().demoTimer).toBeNull();
    });

    it("does NOT clear demoTimer on paused state", () => {
      useOperatorStore.getState().dispatch({
        type: "demo_timer",
        level: "warning",
        message: "5:00 elapsed",
        elapsed: 300,
      });
      expect(useOperatorStore.getState().demoTimer).not.toBeNull();

      useOperatorStore.getState().dispatch({
        type: "state",
        state: "paused",
        team_name: "Team A",
        track: "ROGUE::AGENT",
        started_at: 1700000000,
      });
      // Timer should persist during pause — operator needs to see elapsed time
      expect(useOperatorStore.getState().demoTimer).not.toBeNull();
    });
  });

  describe("pendingCommand lifecycle", () => {
    it("sets pendingCommand when sendCommand is called", () => {
      const mockFn = vi.fn();
      useOperatorStore.getState().setSendCommand(mockFn);
      useOperatorStore.getState().sendCommand("stop_demo");
      expect(useOperatorStore.getState().pendingCommand).toBe("stop_demo");
    });

    it("clears pendingCommand on command_result", () => {
      const mockFn = vi.fn();
      useOperatorStore.getState().setSendCommand(mockFn);
      useOperatorStore.getState().sendCommand("start_demo", { team: "Alpha" });
      expect(useOperatorStore.getState().pendingCommand).toBe("start_demo");

      useOperatorStore.getState().dispatch({
        type: "command_result",
        success: true,
        message: "Demo started",
      });
      expect(useOperatorStore.getState().pendingCommand).toBeNull();
    });

    it("clears pendingCommand on failed command_result too", () => {
      const mockFn = vi.fn();
      useOperatorStore.getState().setSendCommand(mockFn);
      useOperatorStore.getState().sendCommand("start_demo");
      expect(useOperatorStore.getState().pendingCommand).toBe("start_demo");

      useOperatorStore.getState().dispatch({
        type: "command_result",
        success: false,
        message: "Already running",
      });
      expect(useOperatorStore.getState().pendingCommand).toBeNull();
    });

    it("starts as null", () => {
      expect(useOperatorStore.getState().pendingCommand).toBeNull();
    });

    it("auto-clears pendingCommand after 10s timeout", () => {
      const mockFn = vi.fn();
      useOperatorStore.getState().setSendCommand(mockFn);
      useOperatorStore.getState().sendCommand("stop");
      expect(useOperatorStore.getState().pendingCommand).toBe("stop");

      vi.advanceTimersByTime(10_000);
      expect(useOperatorStore.getState().pendingCommand).toBeNull();
    });

    it("sets timeout error in lastCommandResult after 10s", () => {
      const mockFn = vi.fn();
      useOperatorStore.getState().setSendCommand(mockFn);
      useOperatorStore.getState().sendCommand("stop");

      vi.advanceTimersByTime(10_000);
      const result = useOperatorStore.getState().lastCommandResult;
      expect(result).not.toBeNull();
      expect(result!.success).toBe(false);
      expect(result!.message).toMatch(/timed out/i);
    });

    it("does not trigger timeout if command_result arrives first", () => {
      const mockFn = vi.fn();
      useOperatorStore.getState().setSendCommand(mockFn);
      useOperatorStore.getState().sendCommand("start_demo");

      // Server responds after 2s
      vi.advanceTimersByTime(2000);
      useOperatorStore.getState().dispatch({
        type: "command_result",
        success: true,
        message: "Demo started",
      });
      expect(useOperatorStore.getState().pendingCommand).toBeNull();
      expect(useOperatorStore.getState().lastCommandResult?.success).toBe(true);

      // Advance past timeout — should NOT set error
      vi.advanceTimersByTime(10_000);
      // lastCommandResult was auto-cleared by the 3s timer, not replaced by timeout
      expect(useOperatorStore.getState().pendingCommand).toBeNull();
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
