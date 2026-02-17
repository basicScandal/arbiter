import { create } from "zustand";
import type { ArbiterMessage } from "../types/messages";

export type ActiveScreen =
  | "idle"
  | "commentary"
  | "question"
  | "scorecard"
  | "deliberation";

export interface CriterionEntry {
  name: string;
  score: number;
  weight: number;
  justification: string;
}

export interface RankingEntry {
  rank: number;
  teamName: string;
  totalScore: number;
  track: string;
  reasoning: string;
}

export interface DisplayState {
  connected: boolean;
  activeScreen: ActiveScreen;
  // Commentary / Question
  teamName: string;
  commentaryText: string;
  isQuestion: boolean;
  // ScoreCard
  scoreTeamName: string;
  criteria: CriterionEntry[];
  scoreTotal: { teamName: string; totalScore: number; track: string } | null;
  // Deliberation
  rankings: RankingEntry[];
  narrative: string;
  // Actions
  dispatch: (msg: ArbiterMessage) => void;
  setConnected: (connected: boolean) => void;
}

export const useDisplayStore = create<DisplayState>((set) => ({
  connected: false,
  activeScreen: "idle",
  teamName: "",
  commentaryText: "",
  isQuestion: false,
  scoreTeamName: "",
  criteria: [],
  scoreTotal: null,
  rankings: [],
  narrative: "",

  setConnected: (connected) => set({ connected }),

  dispatch: (msg) => {
    switch (msg.type) {
      case "clear":
        set({
          activeScreen: "idle",
          teamName: "",
          commentaryText: "",
          isQuestion: false,
          scoreTeamName: "",
          criteria: [],
          scoreTotal: null,
          rankings: [],
          narrative: "",
        });
        break;

      case "commentary":
        set({
          activeScreen: "commentary",
          teamName: msg.team_name,
          commentaryText: msg.text,
          isQuestion: false,
        });
        break;

      case "question":
        set({
          activeScreen: "question",
          teamName: msg.team_name,
          commentaryText: msg.text,
          isQuestion: true,
        });
        break;

      case "score_intro":
        set({
          activeScreen: "scorecard",
          scoreTeamName: msg.team_name,
          criteria: [],
          scoreTotal: null,
        });
        break;

      case "score_criterion":
        set((state) => ({
          criteria: [
            ...state.criteria,
            {
              name: msg.name,
              score: msg.score,
              weight: msg.weight,
              justification: msg.justification,
            },
          ],
        }));
        break;

      case "score_total":
        set({
          scoreTotal: {
            teamName: msg.team_name,
            totalScore: msg.total_score,
            track: msg.track,
          },
        });
        break;

      case "deliberation_ranking":
        set((state) => ({
          activeScreen: "deliberation",
          rankings: [
            ...state.rankings,
            {
              rank: msg.rank,
              teamName: msg.team_name,
              totalScore: msg.total_score,
              track: msg.track,
              reasoning: msg.reasoning,
            },
          ],
        }));
        break;

      case "deliberation_narrative":
        set({ narrative: msg.narrative });
        break;
    }
  },
}));
