import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScorePanel } from "../ScorePanel";
import { useOperatorStore } from "../../store/operatorStore";

describe("ScorePanel", () => {
  beforeEach(() => {
    useOperatorStore.setState({ lastScorecard: null });
  });

  it("renders SCORE heading", () => {
    render(<ScorePanel />);
    expect(screen.getByText("SCORE")).toBeInTheDocument();
  });

  it("shows awaiting message when no scorecard", () => {
    render(<ScorePanel />);
    expect(screen.getByText("Awaiting judgment...")).toBeInTheDocument();
  });

  it("renders scorecard with team name and total score", () => {
    useOperatorStore.setState({
      lastScorecard: {
        team_name: "Team Alpha",
        track: "SHADOW::VECTOR",
        total_score: 8.5,
        criteria: [
          { name: "Technical Merit", score: 9.0, weight: 0.4, justification: "Excellent" },
          { name: "Innovation", score: 8.0, weight: 0.3, justification: "Good" },
        ],
        track_bonus: null,
      },
    });
    render(<ScorePanel />);
    expect(screen.getByText("Team Alpha")).toBeInTheDocument();
    expect(screen.getByText("8.5")).toBeInTheDocument();
    expect(screen.getByText("Technical Merit")).toBeInTheDocument();
    expect(screen.getByText("9.0")).toBeInTheDocument();
  });

  it("renders track bonus when present", () => {
    useOperatorStore.setState({
      lastScorecard: {
        team_name: "Team Beta",
        track: "SENTINEL::MESH",
        total_score: 7.0,
        criteria: [
          { name: "Technical Merit", score: 7.0, weight: 0.4, justification: "Solid" },
        ],
        track_bonus: { name: "Defense Depth", score: 8.0, weight: 0.15, justification: "Strong defense" },
      },
    });
    render(<ScorePanel />);
    expect(screen.getByText("Defense Depth")).toBeInTheDocument();
    expect(screen.getByText("8.0")).toBeInTheDocument();
  });
});
