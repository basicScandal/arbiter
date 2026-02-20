import { create } from "zustand";
import type { ArbiterMessage } from "../types/messages";

export type ActiveScreen =
  | "idle"
  | "commentary"
  | "question"
  | "scorecard"
  | "deliberation"
  | "thinking"
  | "intermission";

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
  commentarySentences: Array<{ text: string; emotion: string }>;
  isQuestion: boolean;
  // ScoreCard
  scoreTeamName: string;
  criteria: CriterionEntry[];
  scoreTotal: { teamName: string; totalScore: number; track: string } | null;
  // Deliberation
  rankings: RankingEntry[];
  narrative: string;
  // Injection alert overlay
  injectionAlert: { category: string; confidence: string; roast: string; teamName: string } | null;
  // Intermission
  intermissionData: { leaderboard: Array<{ teamName: string; totalScore: number; track: string }>; totalInjections: number } | null;
  // Thinking (capture in progress)
  thinkingTeam: { teamName: string; track: string } | null;
  // Actions
  dispatch: (msg: ArbiterMessage) => void;
  setConnected: (connected: boolean) => void;
}

export const useDisplayStore = create<DisplayState>((set) => ({
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

  setConnected: (connected) => set({ connected }),

  dispatch: (msg) => {
    switch (msg.type) {
      case "clear":
        set({
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
        break;

      case "commentary": {
        const sentenceIndex = msg.sentence_index ?? 0;
        const emotion = msg.emotion ?? "";
        set((state) => {
          const sentences =
            sentenceIndex === 0
              ? [{ text: msg.text, emotion }]
              : [...state.commentarySentences, { text: msg.text, emotion }];
          return {
            activeScreen: "commentary",
            teamName: msg.team_name,
            commentaryText: msg.text,
            commentarySentences: sentences,
            isQuestion: false,
          };
        });
        break;
      }

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
        set((state) => {
          const base = state.activeScreen !== "deliberation" ? [] : state.rankings;
          return {
            activeScreen: "deliberation",
            rankings: [
              ...base,
              {
                rank: msg.rank,
                teamName: msg.team_name,
                totalScore: msg.total_score,
                track: msg.track,
                reasoning: msg.reasoning,
              },
            ],
          };
        });
        break;

      case "deliberation_narrative":
        set({ narrative: msg.narrative });
        break;

      case "capture_started":
        set({
          activeScreen: "thinking",
          thinkingTeam: {
            teamName: msg.team_name,
            track: msg.track,
          },
        });
        break;

      case "injection_blocked":
        set({
          injectionAlert: {
            category: msg.category,
            confidence: msg.confidence,
            roast: msg.roast,
            teamName: msg.team_name,
          },
        });
        setTimeout(() => {
          set((state) => {
            if (state.injectionAlert?.roast === msg.roast) {
              return { injectionAlert: null };
            }
            return {};
          });
        }, 4000);
        break;

      case "intermission":
        set({
          activeScreen: "intermission",
          intermissionData: {
            leaderboard: msg.leaderboard.map((e) => ({
              teamName: e.team_name,
              totalScore: e.total_score,
              track: e.track,
            })),
            totalInjections: msg.total_injections,
          },
        });
        break;
    }
  },
}));
