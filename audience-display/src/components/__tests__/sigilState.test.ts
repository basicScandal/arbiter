import { describe, it, expect } from "vitest";
import { getSigilState, outerRingDashArray } from "../ArbiterSigil";

describe("getSigilState", () => {
  describe("injection alert override", () => {
    it("returns red/fast state regardless of screen when injectionAlert is true", () => {
      const state = getSigilState("commentary", "excited", true);
      expect(state.color.primary).toBe("#ff4444");
      expect(state.color.secondary).toBe("#ff0000");
      expect(state.coreCycleDuration).toBe(0.3);
      expect(state.outerDuration).toBe(2);
      expect(state.opacity).toBe(1.0);
    });

    it("overrides even idle screen", () => {
      const state = getSigilState("idle", undefined, true);
      expect(state.color.primary).toBe("#ff4444");
    });
  });

  describe("thinking screen", () => {
    it("returns cyan color with medium breathing", () => {
      const state = getSigilState("thinking");
      expect(state.color.primary).toBe("#00d4ff");
      expect(state.outerDuration).toBe(4);
      expect(state.coreCycleDuration).toBe(1.5);
      expect(state.opacity).toBe(1.0);
    });
  });

  describe("commentary screen", () => {
    it("uses emotion config when a known emotion is provided", () => {
      const state = getSigilState("commentary", "excited");
      expect(state.color.primary).toBe("#00ff88"); // excited = green
      expect(state.color.intensity).toBe(0.9);
    });

    it("uses default visuals for unknown emotions", () => {
      const state = getSigilState("commentary", "nonexistent_emotion");
      expect(state.color.primary).toBe("#00d4ff"); // default cyan
    });

    it("uses default visuals when no emotion is provided", () => {
      const state = getSigilState("commentary");
      expect(state.color.primary).toBe("#00d4ff");
    });

    it("scales outer ring speed with emotion intensity", () => {
      const highIntensity = getSigilState("commentary", "amazed"); // 0.95
      const lowIntensity = getSigilState("commentary", "content"); // 0.3
      expect(highIntensity.outerDuration).toBeLessThan(lowIntensity.outerDuration);
    });

    it("scales core cycle duration with emotion intensity", () => {
      const highIntensity = getSigilState("commentary", "amazed");
      const lowIntensity = getSigilState("commentary", "content");
      expect(highIntensity.coreCycleDuration).toBeLessThan(
        lowIntensity.coreCycleDuration,
      );
    });
  });

  describe("question screen", () => {
    it("returns orange color with slow pulse", () => {
      const state = getSigilState("question");
      expect(state.color.primary).toBe("#ff8c00");
      expect(state.outerDuration).toBe(10);
      expect(state.opacity).toBe(0.9);
    });
  });

  describe("scorecard screen", () => {
    it("returns gold color with slow rotation", () => {
      const state = getSigilState("scorecard");
      expect(state.color.primary).toBe("#ffd700");
      expect(state.outerDuration).toBe(20);
    });
  });

  describe("deliberation screen", () => {
    it("returns gold/cyan dual color with doubled stroke", () => {
      const state = getSigilState("deliberation");
      expect(state.color.primary).toBe("#ffd700");
      expect(state.color.secondary).toBe("#00d4ff");
      expect(state.strokeMultiplier).toBe(2);
      expect(state.outerDuration).toBe(8);
    });
  });

  describe("idle / intermission / default", () => {
    it("returns low-opacity default state for idle", () => {
      const state = getSigilState("idle");
      expect(state.opacity).toBe(0.4);
      expect(state.outerDuration).toBe(12);
    });

    it("returns same state for intermission", () => {
      const idle = getSigilState("idle");
      const intermission = getSigilState("intermission");
      expect(idle).toEqual(intermission);
    });

    it("returns same state for unknown screens", () => {
      const idle = getSigilState("idle");
      const unknown = getSigilState("some_unknown_screen");
      expect(idle).toEqual(unknown);
    });
  });
});

describe("outerRingDashArray", () => {
  it("returns a dash-gap pattern string", () => {
    const result = outerRingDashArray(180, 12);
    const parts = result.split(" ").map(Number);
    expect(parts).toHaveLength(2);
    expect(parts[0]).toBeGreaterThan(0); // dash
    expect(parts[1]).toBeGreaterThan(0); // gap
  });

  it("dash + gap equals one segment length", () => {
    const r = 180;
    const segments = 12;
    const circumference = 2 * Math.PI * r;
    const segLen = circumference / segments;

    const result = outerRingDashArray(r, segments);
    const [dash, gap] = result.split(" ").map(Number);
    expect(dash + gap).toBeCloseTo(segLen);
  });

  it("dash is 60% and gap is 40% of segment", () => {
    const r = 100;
    const segments = 8;
    const circumference = 2 * Math.PI * r;
    const segLen = circumference / segments;

    const result = outerRingDashArray(r, segments);
    const [dash, gap] = result.split(" ").map(Number);
    expect(dash).toBeCloseTo(segLen * 0.6);
    expect(gap).toBeCloseTo(segLen * 0.4);
  });
});
