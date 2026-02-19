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
  scoringPhase: 'idle' | 'sanitizing' | 'scoring' | 'revealing' | null;
  lastScorecard: {
    team_name: string;
    track: string;
    total_score: number;
    criteria: Array<{name: string; score: number; weight: number; justification: string}>;
    track_bonus: {name: string; score: number; weight: number; justification: string} | null;
  } | null;
  sendCommand: (action: string, params?: Record<string, string>) => void;
  dispatch: (msg: ServerMessage) => void;
  setConnected: (connected: boolean) => void;
  setConnectionState: (state: 'connecting' | 'connected' | 'reconnecting') => void;
  setSendCommand: (fn: (action: string, params?: Record<string, string>) => void) => void;
}

let eventIdCounter = 0;

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
  scoringPhase: null,
  lastScorecard: null,
  sendCommand: () => {},

  setConnected: (connected) => set({ connected, connectionState: connected ? 'connected' : 'reconnecting' }),
  setConnectionState: (connectionState) => set({ connectionState, connected: connectionState === 'connected' }),
  setSendCommand: (fn) => set({ sendCommand: fn }),

  dispatch: (msg) => {
    switch (msg.type) {
      case 'state':
        set({
          demoState: msg.state,
          teamName: msg.team_name,
          track: msg.track,
          startedAt: msg.started_at,
          // Clear stale data on state transitions
          ...(msg.state === 'idle' && { events: [], lastScorecard: null, scoringPhase: null }),
          ...(msg.state === 'capturing' && { lastScorecard: null, scoringPhase: null }),
          ...(msg.state === 'stopped' && { scoringPhase: 'sanitizing' as const }),
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
        // Advance scoring phase based on pipeline events
        if (msg.event_type === 'observation_verified') {
          set({ scoringPhase: 'scoring' });
        }
        // Extract scorecard from scoring_complete events
        if (msg.event_type === 'scoring_complete') {
          if (msg.data?.scorecard) {
            set({ scoringPhase: 'revealing', lastScorecard: msg.data.scorecard as OperatorState['lastScorecard'] });
          } else {
            set({ scoringPhase: 'revealing' });
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
        set({ lastCommandResult: { success: msg.success, message: msg.message } });
        setTimeout(() => set({ lastCommandResult: null }), 3000);
        break;
    }
  },
}));
