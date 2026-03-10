import { create } from "zustand";
import type { ServerMessage } from "../types/protocol";

export interface EventEntry {
  id: number;
  event_type: string;
  timestamp: number;
  data?: Record<string, unknown>;
}

export interface OperatorState {
  connected: boolean;
  connectionState: 'connecting' | 'connected' | 'reconnecting';
  demoState: 'idle' | 'capturing' | 'paused' | 'stopped';
  teamName: string;
  track: string;
  startedAt: number | null;
  counters: {
    frames: number;
    transcripts: number;
    attacks: number;
    clean: number;
  };
  events: EventEntry[];
  lastCommandResult: { success: boolean; message: string; } | null;
  health: Record<string, boolean>;
  demoTimer: { level: 'warning' | 'critical'; message: string; elapsed: number } | null;
  scoringPhase: 'sanitizing' | 'scoring' | 'revealing' | 'failed' | null;
  lastScorecard: {
    team_name: string;
    track: string;
    total_score: number;
    criteria: Array<{name: string; score: number; weight: number; justification: string}>;
    track_bonus: {name: string; score: number; weight: number; justification: string} | null;
  } | null;
  pendingCommand: string | null;
  sendCommand: (action: string, params?: Record<string, string>) => void;
  dispatch: (msg: ServerMessage) => void;
  setConnected: (connected: boolean) => void;
  setConnectionState: (state: 'connecting' | 'connected' | 'reconnecting') => void;
  setSendCommand: (fn: (action: string, params?: Record<string, string>) => void) => void;
}

let eventIdCounter = 0;
let pendingCommandTimer: ReturnType<typeof setTimeout> | null = null;

const PENDING_COMMAND_TIMEOUT_MS = 10_000;

export const useOperatorStore = create<OperatorState>((set) => ({
  connected: false,
  connectionState: 'connecting',
  demoState: 'idle',
  teamName: '',
  track: '',
  startedAt: null,
  counters: {
    frames: 0,
    transcripts: 0,
    attacks: 0,
    clean: 0,
  },
  events: [],
  lastCommandResult: null,
  health: {},
  demoTimer: null,
  scoringPhase: null,
  lastScorecard: null,
  pendingCommand: null,
  sendCommand: () => {},

  setConnected: (connected) => set({ connected, connectionState: connected ? 'connected' : 'reconnecting' }),
  setConnectionState: (connectionState) => set({ connectionState, connected: connectionState === 'connected' }),
  setSendCommand: (fn) => set({
    sendCommand: (action, params) => {
      if (pendingCommandTimer) clearTimeout(pendingCommandTimer);
      set({ pendingCommand: action });
      fn(action, params);
      pendingCommandTimer = setTimeout(() => {
        pendingCommandTimer = null;
        set({
          pendingCommand: null,
          lastCommandResult: { success: false, message: 'Command timed out — no response from server' },
        });
        setTimeout(() => set({ lastCommandResult: null }), 3000);
      }, PENDING_COMMAND_TIMEOUT_MS);
    },
  }),

  dispatch: (msg) => {
    switch (msg.type) {
      case 'state':
        set({
          demoState: msg.state,
          teamName: msg.team_name,
          track: msg.track,
          startedAt: msg.started_at,
          // Clear stale data on state transitions
          ...(msg.state === 'idle' && { events: [], lastScorecard: null, scoringPhase: null, demoTimer: null }),
          ...(msg.state === 'capturing' && { lastScorecard: null, scoringPhase: null, demoTimer: null }),
          ...(msg.state === 'stopped' && { demoTimer: null }),
        });
        break;

      case 'event': {
        set((state) => ({
          events: [
            {
              id: eventIdCounter++,
              event_type: msg.event_type,
              timestamp: msg.timestamp,
              data: msg.data,
            },
            ...state.events,
          ].slice(0, 200),
        }));
        // Extract scorecard from scoring_complete events
        if (msg.event_type === 'scoring_complete') {
          if (msg.data?.scorecard) {
            set({ lastScorecard: msg.data.scorecard as OperatorState['lastScorecard'] });
          }
        }
        break;
      }

      case 'counters':
        set({
          counters: {
            frames: msg.frames,
            transcripts: msg.transcripts,
            attacks: msg.attacks,
            clean: msg.clean,
          },
        });
        break;

      case 'health':
        set({ health: msg.services });
        break;

      case 'command_result':
        if (pendingCommandTimer) {
          clearTimeout(pendingCommandTimer);
          pendingCommandTimer = null;
        }
        set({ lastCommandResult: { success: msg.success, message: msg.message }, pendingCommand: null });
        setTimeout(() => set({ lastCommandResult: null }), 3000);
        break;

      case 'demo_timer':
        set({ demoTimer: { level: msg.level, message: msg.message, elapsed: msg.elapsed } });
        break;

      case 'scoring_phase':
        set({ scoringPhase: msg.phase });
        break;
    }
  },
}));
