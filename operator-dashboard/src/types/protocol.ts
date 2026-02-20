// Client → Server
export interface CommandMessage {
  type: 'command';
  action: string;
  team_name?: string;
  track?: string;
}

// Server → Client
export interface StateMessage {
  type: 'state';
  state: 'idle' | 'capturing' | 'paused' | 'stopped';
  team_name: string;
  track: string;
  started_at: number | null;
}

export interface EventMessage {
  type: 'event';
  event_type: string;
  timestamp: number;
  data?: Record<string, unknown>;
}

export interface CountersMessage {
  type: 'counters';
  frames: number;
  transcripts: number;
  attacks: number;
  clean: number;
}

export interface CommandResultMessage {
  type: 'command_result';
  success: boolean;
  message: string;
}

export interface HealthMessage {
  type: 'health';
  services: Record<string, boolean>;
}

export interface DemoTimerMessage {
  type: 'demo_timer';
  level: 'warning' | 'critical';
  message: string;
  elapsed: number;
  max_duration: number;
}

export type ServerMessage = StateMessage | EventMessage | CountersMessage | CommandResultMessage | HealthMessage | DemoTimerMessage;
