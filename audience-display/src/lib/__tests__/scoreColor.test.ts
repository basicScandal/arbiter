import { describe, it, expect } from "vitest";
import { scoreColor } from "../scoreColor";

describe("scoreColor", () => {
  it("returns red for scores below 4", () => {
    expect(scoreColor(0)).toBe("#ff4444");
    expect(scoreColor(1)).toBe("#ff4444");
    expect(scoreColor(3.99)).toBe("#ff4444");
  });

  it("returns orange for scores 4 to <6", () => {
    expect(scoreColor(4)).toBe("#ff8c00");
    expect(scoreColor(5)).toBe("#ff8c00");
    expect(scoreColor(5.99)).toBe("#ff8c00");
  });

  it("returns gold for scores 6 to <8", () => {
    expect(scoreColor(6)).toBe("#ffd700");
    expect(scoreColor(7)).toBe("#ffd700");
    expect(scoreColor(7.99)).toBe("#ffd700");
  });

  it("returns green for scores 8 and above", () => {
    expect(scoreColor(8)).toBe("#00ff88");
    expect(scoreColor(9)).toBe("#00ff88");
    expect(scoreColor(10)).toBe("#00ff88");
  });

  it("clamps negative scores to 0 (red)", () => {
    expect(scoreColor(-1)).toBe("#ff4444");
    expect(scoreColor(-100)).toBe("#ff4444");
  });

  it("clamps scores above 10 to 10 (green)", () => {
    expect(scoreColor(11)).toBe("#00ff88");
    expect(scoreColor(999)).toBe("#00ff88");
  });

  it("handles exact boundary values", () => {
    expect(scoreColor(4)).toBe("#ff8c00");  // exactly 4 → orange, not red
    expect(scoreColor(6)).toBe("#ffd700");  // exactly 6 → gold, not orange
    expect(scoreColor(8)).toBe("#00ff88");  // exactly 8 → green, not gold
  });
});
