import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { useDisplayStore } from "../displayStore";

describe("displayStore", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useDisplayStore.setState({
      connected: false,
      activeScreen: "idle",
      teamName: "",
      commentaryText: "",
      commentarySentences: [],
      isQuestion: false,
      scoreTeamName: "",
      criteria: [],
      scoreTotal: null,
      rankings: [],
      narrative: "",
      injectionAlert: null,
      intermissionData: null,
      thinkingTeam: null,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe("initial state", () => {
    it("has correct defaults", () => {
      const state = useDisplayStore.getState();
      expect(state.connected).toBe(false);
      expect(state.activeScreen).toBe("idle");
      expect(state.teamName).toBe("");
      expect(state.commentaryText).toBe("");
      expect(state.commentarySentences).toEqual([]);
      expect(state.isQuestion).toBe(false);
      expect(state.scoreTeamName).toBe("");
      expect(state.criteria).toEqual([]);
      expect(state.scoreTotal).toBeNull();
      expect(state.rankings).toEqual([]);
      expect(state.narrative).toBe("");
      expect(state.injectionAlert).toBeNull();
      expect(state.intermissionData).toBeNull();
      expect(state.thinkingTeam).toBeNull();
    });
  });

  describe("setConnected", () => {
    it("sets connected to true", () => {
      useDisplayStore.getState().setConnected(true);
      expect(useDisplayStore.getState().connected).toBe(true);
    });

    it("sets connected to false", () => {
      useDisplayStore.getState().setConnected(true);
      useDisplayStore.getState().setConnected(false);
      expect(useDisplayStore.getState().connected).toBe(false);
    });
  });

  describe("dispatch - clear", () => {
    it("resets all state to defaults", () => {
      // First set some state via other dispatches
      useDisplayStore.getState().dispatch({
        type: "commentary",
        text: "Hello world",
        team_name: "Team A",
        emotion: "excited",
        sentence_index: 0,
      });
      useDisplayStore.getState().setConnected(true);

      // Now clear
      useDisplayStore.getState().dispatch({ type: "clear" });

      const state = useDisplayStore.getState();
      expect(state.activeScreen).toBe("idle");
      expect(state.teamName).toBe("");
      expect(state.commentaryText).toBe("");
      expect(state.commentarySentences).toEqual([]);
      expect(state.isQuestion).toBe(false);
      expect(state.scoreTeamName).toBe("");
      expect(state.criteria).toEqual([]);
      expect(state.scoreTotal).toBeNull();
      expect(state.rankings).toEqual([]);
      expect(state.narrative).toBe("");
      expect(state.injectionAlert).toBeNull();
      expect(state.intermissionData).toBeNull();
      expect(state.thinkingTeam).toBeNull();
      // connected is not reset by clear
      expect(state.connected).toBe(true);
    });
  });

  describe("dispatch - commentary", () => {
    it("sets activeScreen to commentary, teamName, commentaryText, isQuestion=false", () => {
      useDisplayStore.getState().dispatch({
        type: "commentary",
        text: "Great presentation!",
        team_name: "Acme Corp",
        emotion: "positive",
        sentence_index: 0,
      });
      const state = useDisplayStore.getState();
      expect(state.activeScreen).toBe("commentary");
      expect(state.teamName).toBe("Acme Corp");
      expect(state.commentaryText).toBe("Great presentation!");
      expect(state.isQuestion).toBe(false);
    });

    it("resets commentarySentences when sentence_index=0", () => {
      // Put some existing sentences in state
      useDisplayStore.setState({
        commentarySentences: [{ text: "old sentence", emotion: "neutral" }],
      });

      useDisplayStore.getState().dispatch({
        type: "commentary",
        text: "Fresh start",
        team_name: "Team B",
        emotion: "happy",
        sentence_index: 0,
      });

      const { commentarySentences } = useDisplayStore.getState();
      expect(commentarySentences).toHaveLength(1);
      expect(commentarySentences[0]).toEqual({ text: "Fresh start", emotion: "happy" });
    });

    it("appends to commentarySentences when sentence_index>0", () => {
      useDisplayStore.setState({
        commentarySentences: [{ text: "First sentence", emotion: "neutral" }],
      });

      useDisplayStore.getState().dispatch({
        type: "commentary",
        text: "Second sentence",
        team_name: "Team B",
        emotion: "excited",
        sentence_index: 1,
      });

      const { commentarySentences } = useDisplayStore.getState();
      expect(commentarySentences).toHaveLength(2);
      expect(commentarySentences[0]).toEqual({ text: "First sentence", emotion: "neutral" });
      expect(commentarySentences[1]).toEqual({ text: "Second sentence", emotion: "excited" });
    });

    it("defaults emotion to empty string when not provided", () => {
      useDisplayStore.getState().dispatch({
        type: "commentary",
        text: "No emotion here",
        team_name: "Team C",
        sentence_index: 0,
      });
      const { commentarySentences } = useDisplayStore.getState();
      expect(commentarySentences[0].emotion).toBe("");
    });

    it("defaults sentence_index to 0 when not provided (resets sentences)", () => {
      useDisplayStore.setState({
        commentarySentences: [{ text: "old", emotion: "old" }],
      });
      useDisplayStore.getState().dispatch({
        type: "commentary",
        text: "New text",
        team_name: "Team D",
      });
      const { commentarySentences } = useDisplayStore.getState();
      expect(commentarySentences).toHaveLength(1);
      expect(commentarySentences[0].text).toBe("New text");
    });
  });

  describe("dispatch - question", () => {
    it("sets activeScreen to question and isQuestion=true", () => {
      useDisplayStore.getState().dispatch({
        type: "question",
        text: "What is your revenue model?",
        team_name: "Startup X",
      });
      const state = useDisplayStore.getState();
      expect(state.activeScreen).toBe("question");
      expect(state.isQuestion).toBe(true);
      expect(state.teamName).toBe("Startup X");
      expect(state.commentaryText).toBe("What is your revenue model?");
    });
  });

  describe("dispatch - score_intro", () => {
    it("sets activeScreen to scorecard and resets criteria and scoreTotal", () => {
      // Pre-populate criteria and scoreTotal
      useDisplayStore.setState({
        criteria: [{ name: "Innovation", score: 9, weight: 0.5, justification: "Good" }],
        scoreTotal: { teamName: "Old Team", totalScore: 8.5, track: "blue" },
      });

      useDisplayStore.getState().dispatch({
        type: "score_intro",
        team_name: "New Team",
      });

      const state = useDisplayStore.getState();
      expect(state.activeScreen).toBe("scorecard");
      expect(state.scoreTeamName).toBe("New Team");
      expect(state.criteria).toEqual([]);
      expect(state.scoreTotal).toBeNull();
    });
  });

  describe("dispatch - score_criterion", () => {
    it("appends a criterion to the criteria array", () => {
      useDisplayStore.getState().dispatch({
        type: "score_criterion",
        name: "Innovation",
        score: 9,
        weight: 0.4,
        justification: "Very creative approach",
      });

      const { criteria } = useDisplayStore.getState();
      expect(criteria).toHaveLength(1);
      expect(criteria[0]).toEqual({
        name: "Innovation",
        score: 9,
        weight: 0.4,
        justification: "Very creative approach",
      });
    });

    it("accumulates multiple criteria", () => {
      useDisplayStore.getState().dispatch({
        type: "score_criterion",
        name: "Innovation",
        score: 9,
        weight: 0.4,
        justification: "Creative",
      });
      useDisplayStore.getState().dispatch({
        type: "score_criterion",
        name: "Feasibility",
        score: 7,
        weight: 0.3,
        justification: "Somewhat realistic",
      });
      useDisplayStore.getState().dispatch({
        type: "score_criterion",
        name: "Execution",
        score: 8,
        weight: 0.3,
        justification: "Well delivered",
      });

      const { criteria } = useDisplayStore.getState();
      expect(criteria).toHaveLength(3);
      expect(criteria[0].name).toBe("Innovation");
      expect(criteria[1].name).toBe("Feasibility");
      expect(criteria[2].name).toBe("Execution");
    });
  });

  describe("dispatch - score_total", () => {
    it("sets scoreTotal with camelCase fields", () => {
      useDisplayStore.getState().dispatch({
        type: "score_total",
        team_name: "Alpha Team",
        total_score: 8.7,
        track: "ROGUE::AGENT",
      });

      const { scoreTotal } = useDisplayStore.getState();
      expect(scoreTotal).not.toBeNull();
      expect(scoreTotal?.teamName).toBe("Alpha Team");
      expect(scoreTotal?.totalScore).toBe(8.7);
      expect(scoreTotal?.track).toBe("ROGUE::AGENT");
    });
  });

  describe("dispatch - deliberation_ranking", () => {
    it("resets rankings when not already on deliberation screen", () => {
      // Pre-populate rankings on a different screen
      useDisplayStore.setState({
        activeScreen: "scorecard",
        rankings: [
          { rank: 1, teamName: "Old Team", totalScore: 9.0, track: "blue", reasoning: "Top" },
        ],
      });

      useDisplayStore.getState().dispatch({
        type: "deliberation_ranking",
        rank: 1,
        team_name: "New Team",
        total_score: 8.5,
        track: "ROGUE::AGENT",
        reasoning: "Very innovative",
      });

      const state = useDisplayStore.getState();
      expect(state.activeScreen).toBe("deliberation");
      expect(state.rankings).toHaveLength(1);
      expect(state.rankings[0].teamName).toBe("New Team");
    });

    it("appends to rankings when already on deliberation screen", () => {
      useDisplayStore.setState({
        activeScreen: "deliberation",
        rankings: [
          { rank: 1, teamName: "First Place", totalScore: 9.5, track: "red", reasoning: "Best" },
        ],
      });

      useDisplayStore.getState().dispatch({
        type: "deliberation_ranking",
        rank: 2,
        team_name: "Second Place",
        total_score: 8.0,
        track: "blue",
        reasoning: "Good effort",
      });

      const { rankings } = useDisplayStore.getState();
      expect(rankings).toHaveLength(2);
      expect(rankings[0].teamName).toBe("First Place");
      expect(rankings[1].teamName).toBe("Second Place");
      expect(rankings[1].rank).toBe(2);
    });

    it("maps snake_case fields to camelCase", () => {
      useDisplayStore.getState().dispatch({
        type: "deliberation_ranking",
        rank: 1,
        team_name: "Snake Team",
        total_score: 7.5,
        track: "green",
        reasoning: "Solid pitch",
      });

      const entry = useDisplayStore.getState().rankings[0];
      expect(entry.teamName).toBe("Snake Team");
      expect(entry.totalScore).toBe(7.5);
      expect(entry.track).toBe("green");
      expect(entry.reasoning).toBe("Solid pitch");
    });
  });

  describe("dispatch - deliberation_narrative", () => {
    it("sets the narrative text", () => {
      useDisplayStore.getState().dispatch({
        type: "deliberation_narrative",
        narrative: "After careful consideration, the judges have reached a verdict.",
      });

      expect(useDisplayStore.getState().narrative).toBe(
        "After careful consideration, the judges have reached a verdict.",
      );
    });
  });

  describe("dispatch - capture_started", () => {
    it("sets activeScreen to thinking and sets thinkingTeam", () => {
      useDisplayStore.getState().dispatch({
        type: "capture_started",
        team_name: "Cyber Squad",
        track: "SHADOW::VECTOR",
      });

      const state = useDisplayStore.getState();
      expect(state.activeScreen).toBe("thinking");
      expect(state.thinkingTeam).toEqual({
        teamName: "Cyber Squad",
        track: "SHADOW::VECTOR",
      });
    });
  });

  describe("dispatch - injection_blocked", () => {
    it("sets injectionAlert with all fields", () => {
      useDisplayStore.getState().dispatch({
        type: "injection_blocked",
        category: "prompt_injection",
        confidence: "high",
        roast: "Nice try, hacker.",
        team_name: "Evil Corp",
      });

      const { injectionAlert } = useDisplayStore.getState();
      expect(injectionAlert).not.toBeNull();
      expect(injectionAlert?.category).toBe("prompt_injection");
      expect(injectionAlert?.confidence).toBe("high");
      expect(injectionAlert?.roast).toBe("Nice try, hacker.");
      expect(injectionAlert?.teamName).toBe("Evil Corp");
    });

    it("auto-clears injectionAlert after 4000ms", () => {
      useDisplayStore.getState().dispatch({
        type: "injection_blocked",
        category: "jailbreak",
        confidence: "medium",
        roast: "Not today.",
        team_name: "Shady LLC",
      });

      expect(useDisplayStore.getState().injectionAlert).not.toBeNull();

      vi.advanceTimersByTime(3999);
      expect(useDisplayStore.getState().injectionAlert).not.toBeNull();

      vi.advanceTimersByTime(1);
      expect(useDisplayStore.getState().injectionAlert).toBeNull();
    });

    it("does not clear a newer alert if a different injection arrives after", () => {
      useDisplayStore.getState().dispatch({
        type: "injection_blocked",
        category: "jailbreak",
        confidence: "high",
        roast: "First roast.",
        team_name: "Team A",
      });

      vi.advanceTimersByTime(2000);

      // Second injection arrives — overwrites alert
      useDisplayStore.getState().dispatch({
        type: "injection_blocked",
        category: "prompt_injection",
        confidence: "low",
        roast: "Second roast.",
        team_name: "Team B",
      });

      // The first timeout fires at 4000ms but roast has changed, so it should NOT clear
      vi.advanceTimersByTime(2000); // 4000ms total for first dispatch
      expect(useDisplayStore.getState().injectionAlert).not.toBeNull();
      expect(useDisplayStore.getState().injectionAlert?.roast).toBe("Second roast.");
    });
  });

  describe("dispatch - intermission", () => {
    it("sets activeScreen to intermission and maps leaderboard snake_case to camelCase", () => {
      useDisplayStore.getState().dispatch({
        type: "intermission",
        leaderboard: [
          { team_name: "Alpha", total_score: 9.5, track: "ROGUE::AGENT" },
          { team_name: "Beta", total_score: 8.0, track: "SHADOW::VECTOR" },
        ],
        total_injections: 7,
      });

      const state = useDisplayStore.getState();
      expect(state.activeScreen).toBe("intermission");
      expect(state.intermissionData).not.toBeNull();
      expect(state.intermissionData?.totalInjections).toBe(7);

      const lb = state.intermissionData?.leaderboard;
      expect(lb).toHaveLength(2);
      expect(lb?.[0]).toEqual({ teamName: "Alpha", totalScore: 9.5, track: "ROGUE::AGENT" });
      expect(lb?.[1]).toEqual({ teamName: "Beta", totalScore: 8.0, track: "SHADOW::VECTOR" });
    });

    it("handles empty leaderboard", () => {
      useDisplayStore.getState().dispatch({
        type: "intermission",
        leaderboard: [],
        total_injections: 0,
      });

      const state = useDisplayStore.getState();
      expect(state.activeScreen).toBe("intermission");
      expect(state.intermissionData?.leaderboard).toEqual([]);
      expect(state.intermissionData?.totalInjections).toBe(0);
    });
  });
});
