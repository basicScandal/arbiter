"""Integration tests for circuit breaker wiring in scoring and commentary engines."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.resilience.circuit_breaker import GeminiCircuitBreaker
from src.resilience.retry import DailyQuotaExhausted


# ---------------------------------------------------------------------------
# Scoring engine + circuit breaker
# ---------------------------------------------------------------------------


class TestScoringCircuitBreaker:
    """Tests for circuit breaker integration in ScoringEngine."""

    @pytest.mark.asyncio
    async def test_skips_gemini_when_breaker_tripped(self):
        """When circuit breaker is tripped, Gemini is never called."""
        from src.scoring.engine import ScoringEngine
        from src.defense.models import SanitizedOutput

        cb = GeminiCircuitBreaker()
        cb.trip()
        engine = ScoringEngine(api_key="test-key", anthropic_api_key="sk-test", circuit_breaker=cb)

        gemini_mock = AsyncMock()
        claude_mock = AsyncMock(return_value='{"criteria": [{"name": "Technical Execution", "score": 7.0, "justification": "Good"}], "track_bonus": null}')

        sanitized = SanitizedOutput(
            team_name="TestTeam",
            observations=["Built a tool"],
            transcripts=["We built this"],
            injection_attempts=[],
            demo_duration=180.0,
        )

        with (
            patch.object(engine, "_call_gemini", new=gemini_mock),
            patch.object(engine, "_call_claude", new=claude_mock),
        ):
            await engine.score(sanitized, "ROGUE::AGENT")

        gemini_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_trips_breaker_on_daily_quota(self):
        """DailyQuotaExhausted from scoring should trip the shared breaker."""
        from src.scoring.engine import ScoringEngine
        from src.defense.models import SanitizedOutput

        cb = GeminiCircuitBreaker()
        assert cb.available is True

        engine = ScoringEngine(api_key="test-key", anthropic_api_key="sk-test", circuit_breaker=cb)

        sanitized = SanitizedOutput(
            team_name="TestTeam",
            observations=["Built a tool"],
            transcripts=["We built this"],
            injection_attempts=[],
            demo_duration=180.0,
        )

        claude_mock = AsyncMock(return_value='{"criteria": [{"name": "Technical Execution", "score": 7.0, "justification": "Good"}], "track_bonus": null}')

        with (
            patch.object(engine, "_call_gemini", new=AsyncMock(side_effect=DailyQuotaExhausted("quota"))),
            patch.object(engine, "_call_claude", new=claude_mock),
        ):
            await engine.score(sanitized, "ROGUE::AGENT")

        assert cb.available is False

    def test_works_without_breaker(self):
        """Engine should work normally when no circuit breaker is provided."""
        from src.scoring.engine import ScoringEngine

        engine = ScoringEngine(api_key="test-key")
        assert engine._circuit_breaker is None


# ---------------------------------------------------------------------------
# Commentary engine + circuit breaker
# ---------------------------------------------------------------------------


class TestCommentaryCircuitBreaker:
    """Tests for circuit breaker integration in CommentaryGenerator."""

    @pytest.mark.asyncio
    async def test_skips_gemini_when_breaker_tripped(self):
        """When circuit breaker is tripped, Gemini is never called."""
        from src.commentary.generator import CommentaryGenerator
        from src.defense.models import SanitizedOutput

        cb = GeminiCircuitBreaker()
        cb.trip()
        gen = CommentaryGenerator(api_key="test-key", groq_api_key="gsk-test", circuit_breaker=cb)

        gemini_mock = AsyncMock()
        groq_mock = AsyncMock(return_value="Great demo by the team.")

        sanitized = SanitizedOutput(
            team_name="TestTeam",
            observations=["Built a tool"],
            transcripts=["We built this"],
            injection_attempts=[],
            demo_duration=180.0,
        )

        with (
            patch.object(gen, "_stream_gemini", new=gemini_mock),
            patch.object(gen, "_call_groq", new=groq_mock),
        ):
            result = await gen.generate(sanitized)

        gemini_mock.assert_not_called()
        assert result.text == "Great demo by the team."

    @pytest.mark.asyncio
    async def test_trips_breaker_on_daily_quota(self):
        """DailyQuotaExhausted from commentary should trip the shared breaker."""
        from src.commentary.generator import CommentaryGenerator
        from src.defense.models import SanitizedOutput

        cb = GeminiCircuitBreaker()
        gen = CommentaryGenerator(api_key="test-key", groq_api_key="gsk-test", circuit_breaker=cb)

        sanitized = SanitizedOutput(
            team_name="TestTeam",
            observations=["Built a tool"],
            transcripts=["We built this"],
            injection_attempts=[],
            demo_duration=180.0,
        )

        with (
            patch.object(gen, "_stream_gemini", new=AsyncMock(side_effect=DailyQuotaExhausted("quota"))),
            patch.object(gen, "_call_groq", new=AsyncMock(return_value="Fallback commentary.")),
        ):
            result = await gen.generate(sanitized)

        assert cb.available is False
        assert result.text == "Fallback commentary."


# ---------------------------------------------------------------------------
# Deliberation engine + circuit breaker
# ---------------------------------------------------------------------------


class TestDeliberationCircuitBreaker:
    """Tests for circuit breaker integration in DeliberationEngine."""

    @pytest.mark.asyncio
    async def test_skips_gemini_when_breaker_tripped(self):
        """When circuit breaker is tripped, Gemini is never called for deliberation."""
        from src.memory.deliberation_engine import DeliberationEngine
        from src.memory.models import DemoMemory, DeliberationResult, TeamRanking
        from src.scoring.models import CriterionScore, DemoScorecard

        cb = GeminiCircuitBreaker()
        cb.trip()
        engine = DeliberationEngine(api_key="test-key", anthropic_api_key="sk-test", circuit_breaker=cb)

        mock_result = DeliberationResult(
            rankings=[TeamRanking(
                rank=1, team_name="TestTeam", track="ROGUE::AGENT",
                total_score=7.0, strengths=["Good"], weaknesses=["None"],
                cross_references=[], reasoning="Solid",
            )],
            overall_narrative="Good event.",
            notable_themes=["AI"],
            deliberated_at=0.0,
        )

        gemini_mock = AsyncMock()

        memory = DemoMemory(
            team_name="TestTeam", track="ROGUE::AGENT",
            observations=["Built a tool"], transcripts=["We built this"],
            injection_attempts=0, demo_duration=180.0, stored_at=1000.0,
        )
        scorecard = DemoScorecard(
            team_name="TestTeam", track="ROGUE::AGENT",
            criteria=[CriterionScore(name="Technical Execution", score=7.0, weight=0.4, justification="Good")],
            track_bonus=None, total_score=7.0, scored_at=1000.0,
        )

        with (
            patch.object(engine, "_call_gemini", new=gemini_mock),
            patch.object(engine, "_call_claude", new=AsyncMock(return_value=mock_result)),
        ):
            result = await engine.deliberate(memories=[memory], scorecards=[scorecard])

        gemini_mock.assert_not_called()
        assert isinstance(result, DeliberationResult)


# ---------------------------------------------------------------------------
# Cross-component propagation
# ---------------------------------------------------------------------------


class TestCrossComponentPropagation:
    """Test that tripping the breaker in one engine affects all others."""

    def test_scoring_trip_affects_commentary(self):
        """When scoring trips the breaker, commentary should see it."""
        from src.scoring.engine import ScoringEngine
        from src.commentary.generator import CommentaryGenerator

        cb = GeminiCircuitBreaker()
        scorer = ScoringEngine(api_key="test-key", circuit_breaker=cb)
        commentator = CommentaryGenerator(api_key="test-key", circuit_breaker=cb)

        assert cb.available is True
        cb.trip()  # simulates scoring triggering this
        assert scorer._circuit_breaker.available is False
        assert commentator._circuit_breaker.available is False
