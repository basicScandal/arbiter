export interface ClearMessage {
  type: "clear";
}

export interface CommentaryMessage {
  type: "commentary";
  text: string;
  team_name: string;
}

export interface QuestionMessage {
  type: "question";
  text: string;
  team_name: string;
}

export interface ScoreIntroMessage {
  type: "score_intro";
  team_name: string;
}

export interface ScoreCriterionMessage {
  type: "score_criterion";
  name: string;
  score: number;
  weight: number;
  justification: string;
}

export interface ScoreTotalMessage {
  type: "score_total";
  team_name: string;
  total_score: number;
  track: string;
}

export interface DeliberationRankingMessage {
  type: "deliberation_ranking";
  rank: number;
  team_name: string;
  total_score: number;
  track: string;
  reasoning: string;
}

export interface DeliberationNarrativeMessage {
  type: "deliberation_narrative";
  narrative: string;
}

export type ArbiterMessage =
  | ClearMessage
  | CommentaryMessage
  | QuestionMessage
  | ScoreIntroMessage
  | ScoreCriterionMessage
  | ScoreTotalMessage
  | DeliberationRankingMessage
  | DeliberationNarrativeMessage;
