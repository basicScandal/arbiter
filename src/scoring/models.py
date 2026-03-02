"""Pydantic data models for the scoring pipeline.

Defines types for rubric criteria, track-specific criteria, per-criterion
scores, complete demo scorecards, and scoring-layer capture events.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.capture.models import CaptureEvent

# ---------------------------------------------------------------------------
# Core scoring types
# ---------------------------------------------------------------------------


class RubricCriterion(BaseModel):
    """A single scoring criterion with weight and level descriptors."""

    name: str
    weight: float
    description: str
    levels: dict[str, str]  # "9-10" -> description of that score range


class TrackCriteria(BaseModel):
    """Track-specific scoring criterion for NEBULA:FOG challenge tracks."""

    track_id: str  # e.g., "SHADOW::VECTOR"
    name: str  # e.g., "Attack Effectiveness"
    description: str
    bonus_weight: float  # additional weight on top of general criteria


class CriterionScore(BaseModel):
    """Score for a single rubric criterion."""

    name: str
    score: float = Field(ge=0, le=10)
    weight: float
    justification: str


class DemoScorecard(BaseModel):
    """Complete scorecard for one demo evaluation."""

    team_name: str
    track: str
    criteria: list[CriterionScore]
    track_bonus: CriterionScore | None = None
    total_score: float
    scored_at: float


# ---------------------------------------------------------------------------
# Scoring events extending CaptureEvent
# ---------------------------------------------------------------------------


class ScoringComplete(CaptureEvent):
    """Emitted when scoring finishes for a demo."""

    event_type: str = "scoring_complete"
    scorecard: DemoScorecard


class ScoreRevealed(CaptureEvent):
    """Emitted when a score reveal sequence completes on the display."""

    event_type: str = "score_revealed"
    team_name: str
