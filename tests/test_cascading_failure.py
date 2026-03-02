"""Cascading failure integration tests.

Proves the system degrades gracefully rather than hanging when Gemini
goes down. Validates that fallback chains activate correctly and the
shared circuit breaker prevents repeated Gemini calls across components.

Phase 1, Item 2 of the real-world testing strategy.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.commentary.generator import CommentaryGenerator
from src.defense.models import SanitizedOutput
from src.resilience.circuit_breaker import GeminiCircuitBreaker
from src.scoring.engine import ScoringEngine


def _make_sanitized(team_name: str = "ChaosTeam") -> SanitizedOutput:
    """Create a minimal SanitizedOutput for testing."""
    return SanitizedOutput(
        team_name=team_name,
        observations=["Built a network scanner", "Demonstrated live exploit"],
        transcripts=["We built a scanner that finds open ports"],
        injection_attempts=[],
        demo_duration=180.0,
    )


# Valid JSON that ScoringEngine._parse_and_validate can parse
_CLAUDE_SCORING_JSON = (
    '{"criteria": ['
    '{"name": "Technical Execution", "score": 7.0, "justification": "Solid implementation"},'
    '{"name": "Innovation", "score": 6.5, "justification": "Good approach"},'
    '{"name": "Security Impact", "score": 8.0, "justification": "Real-world impact"},'
    '{"name": "Presentation", "score": 7.0, "justification": "Clear demo"}'
    ']}'
)


@pytest.mark.integration
class TestCascadingFailure:
    """Tests proving graceful degradation when Gemini is unavailable."""

    @pytest.mark.asyncio
    async def test_gemini_down_scoring_falls_to_claude_fallback(self):
        """When Gemini fails, ScoringEngine returns a scorecard via Claude."""
        cb = GeminiCircuitBreaker()
        engine = ScoringEngine(
            api_key="test-key",
            anthropic_api_key="sk-test",
            circuit_breaker=cb,
        )

        with (
            patch.object(
                engine, "_call_gemini",
                new=AsyncMock(side_effect=ConnectionError("Gemini down")),
            ),
            patch.object(
                engine, "_call_claude",
                new=AsyncMock(return_value=_CLAUDE_SCORING_JSON),
            ),
        ):
            scorecard = await engine.score(_make_sanitized(), "SHADOW::VECTOR")

        assert scorecard.team_name == "ChaosTeam"
        assert scorecard.total_score > 0
        assert any(c.name == "Technical Execution" for c in scorecard.criteria)

    @pytest.mark.asyncio
    async def test_gemini_down_commentary_falls_to_groq_fallback(self):
        """When Gemini fails, CommentaryGenerator uses Groq fallback."""
        cb = GeminiCircuitBreaker()
        gen = CommentaryGenerator(
            api_key="test-key",
            groq_api_key="gsk-test",
            circuit_breaker=cb,
        )

        with (
            patch.object(
                gen, "_stream_gemini",
                new=AsyncMock(side_effect=ConnectionError("Gemini down")),
            ),
            patch.object(
                gen, "_call_groq",
                new=AsyncMock(return_value="Groq fallback commentary. Solid demo."),
            ),
        ):
            result = await gen.generate(_make_sanitized())

        assert "Groq fallback" in result.text
        assert len(result.sentences) >= 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_shared_across_scoring_and_commentary(self):
        """Tripping the breaker from scoring makes commentary skip Gemini."""
        cb = GeminiCircuitBreaker()
        scorer = ScoringEngine(
            api_key="test-key",
            anthropic_api_key="sk-test",
            circuit_breaker=cb,
        )
        gen = CommentaryGenerator(
            api_key="test-key",
            groq_api_key="gsk-test",
            circuit_breaker=cb,
        )

        # Trip breaker via scoring failure
        gemini_score_mock = AsyncMock(side_effect=ConnectionError("Gemini down"))
        claude_score_mock = AsyncMock(return_value=_CLAUDE_SCORING_JSON)

        with (
            patch.object(scorer, "_call_gemini", new=gemini_score_mock),
            patch.object(scorer, "_call_claude", new=claude_score_mock),
        ):
            await scorer.score(_make_sanitized(), "SHADOW::VECTOR")

        # Breaker should be tripped now
        assert not cb.available

        # Commentary should skip Gemini entirely
        gemini_gen_mock = AsyncMock()
        groq_mock = AsyncMock(return_value="Fallback commentary here.")

        with (
            patch.object(gen, "_stream_gemini", new=gemini_gen_mock),
            patch.object(gen, "_call_groq", new=groq_mock),
        ):
            result = await gen.generate(_make_sanitized())

        gemini_gen_mock.assert_not_called()
        assert result.text == "Fallback commentary here."

    @pytest.mark.asyncio
    async def test_full_pipeline_completes_with_all_primaries_down(self):
        """Full pipeline completes within 10s even with all Gemini calls failing."""
        cb = GeminiCircuitBreaker()
        scorer = ScoringEngine(
            api_key="test-key",
            anthropic_api_key="sk-test",
            circuit_breaker=cb,
        )
        gen = CommentaryGenerator(
            api_key="test-key",
            groq_api_key="gsk-test",
            circuit_breaker=cb,
        )

        sanitized = _make_sanitized()

        with (
            # All Gemini calls fail
            patch.object(
                scorer, "_call_gemini",
                new=AsyncMock(side_effect=ConnectionError("Gemini down")),
            ),
            patch.object(
                gen, "_stream_gemini",
                new=AsyncMock(side_effect=ConnectionError("Gemini down")),
            ),
            # Fallbacks succeed
            patch.object(
                scorer, "_call_claude",
                new=AsyncMock(return_value=_CLAUDE_SCORING_JSON),
            ),
            patch.object(
                gen, "_call_groq",
                new=AsyncMock(return_value="The demo was solid despite the chaos."),
            ),
        ):
            async with asyncio.timeout(10):
                scorecard = await scorer.score(sanitized, "SHADOW::VECTOR")
                commentary = await gen.generate(sanitized)

        assert scorecard.total_score > 0
        assert commentary.text.strip() != ""
        assert len(commentary.sentences) >= 1
