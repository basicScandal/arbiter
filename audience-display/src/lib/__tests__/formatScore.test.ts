import { describe, it, expect } from "vitest";
import { formatScore } from "../formatScore";

describe("formatScore", () => {
  it("formats integer scores with one decimal place", () => {
    expect(formatScore(8)).toBe("8.0 / 10");
    expect(formatScore(10)).toBe("10.0 / 10");
    expect(formatScore(0)).toBe("0.0 / 10");
  });

  it("formats decimal scores with one decimal place", () => {
    expect(formatScore(7.5)).toBe("7.5 / 10");
    expect(formatScore(9.2)).toBe("9.2 / 10");
  });

  it("rounds to one decimal place", () => {
    expect(formatScore(8.75)).toBe("8.8 / 10");
    expect(formatScore(6.44)).toBe("6.4 / 10");
    expect(formatScore(6.45)).toBe("6.5 / 10");
  });
});
