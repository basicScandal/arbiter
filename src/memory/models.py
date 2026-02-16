"""Pydantic data models for the memory and deliberation system.

Defines types for per-demo structured observations (DemoMemory), team
rankings, deliberation results, and deliberation-layer capture events.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.capture.models import CaptureEvent


# ---------------------------------------------------------------------------
# Core memory types
# ---------------------------------------------------------------------------


class DemoMemory(BaseModel):
    """Structured observations stored per-demo for deliberation.

    Stores clean observations and transcripts (from SanitizedOutput),
    injection attempt count (not content -- security: don't persist
    injection payloads), and timing metadata.
    """

    team_name: str
    track: str
    observations: list[str]  # clean Gemini observations (from SanitizedOutput)
    transcripts: list[str]  # clean transcript segments (from SanitizedOutput)
    injection_attempts: int  # count only, not content
    demo_duration: float  # seconds
    stored_at: float  # timestamp when memory was persisted


class TeamRanking(BaseModel):
    """A single team's ranking within a deliberation result.

    Rank is Python-assigned (never trust LLM). Total score comes from
    ScoreStore (authoritative). LLM provides qualitative analysis only.
    """

    rank: int  # Python-assigned rank (never trust LLM)
    team_name: str
    track: str
    total_score: float  # from ScoreStore (authoritative)
    strengths: list[str]  # 2-3 key strengths from LLM
    weaknesses: list[str]  # 1-2 areas of weakness from LLM
    cross_references: list[str]  # specific comparisons to other teams
    reasoning: str  # why this rank, with evidence


class DeliberationResult(BaseModel):
    """Complete result from the Arbiter's deliberation across all demos."""

    rankings: list[TeamRanking]
    overall_narrative: str  # 2-3 paragraph event summary with Arbiter's voice
    notable_themes: list[str]  # patterns across demos
    deliberated_at: float


# ---------------------------------------------------------------------------
# Deliberation events extending CaptureEvent
# ---------------------------------------------------------------------------


class DeliberationRequested(CaptureEvent):
    """Emitted when the operator requests deliberation."""

    event_type: str = "deliberation_requested"


class DeliberationComplete(CaptureEvent):
    """Emitted when deliberation finishes with rankings and narrative."""

    event_type: str = "deliberation_complete"
    result: DeliberationResult
