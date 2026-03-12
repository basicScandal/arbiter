"""Shared test factories for common mock objects and fixtures.

Consolidates helpers that were previously copy-pasted across 10+ test files.
Import from here instead of redefining locally.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from src.commentary.display_server import DisplayServer
from src.scoring.models import CriterionScore, DemoScorecard


def make_scorecard(
    team_name: str = "TestTeam",
    track: str = "ROGUE::AGENT",
    total_score: float = 7.1,
    scored_at: float = 1000.0,
) -> DemoScorecard:
    """Create a standard test scorecard with 3 criteria."""
    return DemoScorecard(
        team_name=team_name,
        track=track,
        criteria=[
            CriterionScore(
                name="Technical Execution", score=8.0, weight=0.40,
                justification="Solid implementation",
            ),
            CriterionScore(
                name="Innovation", score=7.0, weight=0.30,
                justification="Novel approach",
            ),
            CriterionScore(
                name="Demo Quality", score=6.0, weight=0.30,
                justification="Good presentation",
            ),
        ],
        track_bonus=None,
        total_score=total_score,
        scored_at=scored_at,
    )


def make_mock_gemini(observations: list[str] | None = None) -> MagicMock:
    """Create a mock GeminiSession returning canned observations."""
    gemini = MagicMock()
    gemini.get_observations.return_value = observations or []
    gemini.clear_observations = MagicMock()
    return gemini


def make_mock_display() -> MagicMock:
    """Create a mock DisplayServer with all async methods stubbed."""
    display = MagicMock(spec=DisplayServer)
    display.start = AsyncMock()
    display.stop = AsyncMock()
    display.push_commentary = AsyncMock()
    display.push_score_intro = AsyncMock()
    display.push_criterion_reveal = AsyncMock()
    display.push_total_score = AsyncMock()
    display.push_deliberation_ranking = AsyncMock()
    display.push_deliberation_narrative = AsyncMock()
    display.push_injection_blocked = AsyncMock()
    display.push_intermission = AsyncMock()
    display.push_capture_started = AsyncMock()
    display.clear = AsyncMock()
    return display
