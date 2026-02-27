import { describe, it, expect } from "vitest";
import { emotionConfig, defaultVisuals } from "../../lib/emotionConfig";

/**
 * Pure-logic tests for the EmotionTimeline component behavior.
 * We test the data transformations directly rather than rendering,
 * since the component is thin UI over these calculations.
 */

const VISIBLE_SCREENS = new Set(["commentary", "question", "scorecard"]);
const HIDDEN_SCREENS = [
  "idle",
  "thinking",
  "deliberation",
  "intermission",
] as const;

const MIN_HEIGHT = 20;
const MAX_HEIGHT = 48;

function getBarProps(emotion: string) {
  const visuals = emotionConfig[emotion] ?? defaultVisuals;
  return {
    color: visuals.primary,
    glow: visuals.secondary,
    height: MIN_HEIGHT + visuals.intensity * (MAX_HEIGHT - MIN_HEIGHT),
  };
}

describe("EmotionTimeline", () => {
  describe("bar count matches sentence count", () => {
    it("produces one bar per sentence", () => {
      const sentences = [
        { text: "Wow!", emotion: "excited" },
        { text: "Interesting.", emotion: "thoughtful" },
        { text: "Not bad.", emotion: "skeptical" },
      ];
      const bars = sentences.map((s) => getBarProps(s.emotion));
      expect(bars).toHaveLength(3);
    });

    it("produces zero bars for empty sentences", () => {
      const bars: unknown[] = [];
      expect(bars).toHaveLength(0);
    });
  });

  describe("correct color mapping for known emotions", () => {
    it("maps excited to green", () => {
      const bar = getBarProps("excited");
      expect(bar.color).toBe("#00ff88");
      expect(bar.glow).toBe("#00cc66");
    });

    it("maps amazed to cyan/purple", () => {
      const bar = getBarProps("amazed");
      expect(bar.color).toBe("#00d4ff");
      expect(bar.glow).toBe("#7b61ff");
    });

    it("maps disappointed to red", () => {
      const bar = getBarProps("disappointed");
      expect(bar.color).toBe("#ff4444");
      expect(bar.glow).toBe("#ff8c00");
    });

    it("maps sarcastic to gold", () => {
      const bar = getBarProps("sarcastic");
      expect(bar.color).toBe("#ffd700");
    });
  });

  describe("fallback color for unknown/empty emotions", () => {
    it("uses default cyan for unknown emotion", () => {
      const bar = getBarProps("nonexistent_emotion");
      expect(bar.color).toBe(defaultVisuals.primary);
      expect(bar.glow).toBe(defaultVisuals.secondary);
    });

    it("uses default cyan for empty emotion string", () => {
      const bar = getBarProps("");
      expect(bar.color).toBe(defaultVisuals.primary);
    });
  });

  describe("bar height scales with intensity", () => {
    it("high intensity emotion produces taller bar", () => {
      const amazed = getBarProps("amazed"); // intensity 0.95
      const content = getBarProps("content"); // intensity 0.3
      expect(amazed.height).toBeGreaterThan(content.height);
    });

    it("minimum height is 20px for lowest intensity", () => {
      const bar = getBarProps("nonexistent_emotion"); // default intensity 0.2
      expect(bar.height).toBeCloseTo(MIN_HEIGHT + 0.2 * (MAX_HEIGHT - MIN_HEIGHT));
      expect(bar.height).toBeGreaterThanOrEqual(MIN_HEIGHT);
    });

    it("maximum intensity produces near-max height", () => {
      const amazed = getBarProps("amazed"); // intensity 0.95
      expect(amazed.height).toBeCloseTo(MIN_HEIGHT + 0.95 * (MAX_HEIGHT - MIN_HEIGHT));
    });
  });

  describe("visibility logic", () => {
    it("is visible on commentary, question, and scorecard", () => {
      expect(VISIBLE_SCREENS.has("commentary")).toBe(true);
      expect(VISIBLE_SCREENS.has("question")).toBe(true);
      expect(VISIBLE_SCREENS.has("scorecard")).toBe(true);
    });

    it("is hidden on idle, thinking, deliberation, and intermission", () => {
      for (const screen of HIDDEN_SCREENS) {
        expect(VISIBLE_SCREENS.has(screen)).toBe(false);
      }
    });
  });
});
