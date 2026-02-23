export interface EmotionVisuals {
  primary: string; // hex color for middle ring + inner core
  secondary: string; // hex color for ambient glow
  intensity: number; // 0-1, drives ring speed and core scale
}

export const emotionConfig: Record<string, EmotionVisuals> = {
  // Warm/positive
  excited: { primary: "#00ff88", secondary: "#00cc66", intensity: 0.9 },
  amazed: { primary: "#00d4ff", secondary: "#7b61ff", intensity: 0.95 },
  impressed: { primary: "#00d4ff", secondary: "#00ff88", intensity: 0.7 },
  proud: { primary: "#ffd700", secondary: "#ff8c00", intensity: 0.75 },
  encouraging: { primary: "#00ff88", secondary: "#00d4ff", intensity: 0.5 },
  supportive: { primary: "#00d4ff", secondary: "#a8b2d0", intensity: 0.4 },
  content: { primary: "#a8b2d0", secondary: "#00d4ff", intensity: 0.3 },
  // Cool/analytical
  confident: { primary: "#00d4ff", secondary: "#f0f0f0", intensity: 0.6 },
  thoughtful: { primary: "#7b61ff", secondary: "#a8b2d0", intensity: 0.45 },
  curious: { primary: "#ff8c00", secondary: "#ffd700", intensity: 0.55 },
  constructive: { primary: "#00ff88", secondary: "#ffd700", intensity: 0.5 },
  // Edge/negative
  sarcastic: { primary: "#ffd700", secondary: "#ff8c00", intensity: 0.65 },
  ironic: { primary: "#ff8c00", secondary: "#ffd700", intensity: 0.6 },
  skeptical: { primary: "#ff8c00", secondary: "#ff4444", intensity: 0.55 },
  disappointed: { primary: "#ff4444", secondary: "#ff8c00", intensity: 0.7 },
  surprised: { primary: "#7b61ff", secondary: "#00d4ff", intensity: 0.85 },
};

export const defaultVisuals: EmotionVisuals = {
  primary: "#00d4ff", // cyan accent — arbiter default
  secondary: "#1a1a2e", // bg color
  intensity: 0.2,
};
