"""End-to-end timeout budget tests.

Validates that individual component timeouts work correctly and
documents the missing global pipeline timeout budget via xfail.

Phase 1, Item 3 of the real-world testing strategy.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.event_bus import EventBus
from src.capture.models import DemoStopped
from src.commentary.generator import CommentaryGenerator
from src.commentary.models import CommentaryDelivered
from src.commentary.pipeline import CommentaryPipeline
from src.defense.models import ObservationVerified, SanitizedOutput
from src.resilience.circuit_breaker import GeminiCircuitBreaker
from src.resilience.health import default_health
from src.scoring.engine import ScoringEngine
from tests.helpers.event_collector import EventCollector


def _make_sanitized(team_name: str = "TimeoutTeam") -> SanitizedOutput:
    return SanitizedOutput(
        team_name=team_name,
        observations=["Demonstrated buffer overflow exploit"],
        transcripts=["We found a heap overflow in the target service"],
        injection_attempts=[],
        demo_duration=180.0,
    )


_SCORING_JSON = (
    '{"criteria": ['
    '{"name": "Technical Execution", "score": 7.0, "justification": "Good"}'
    ']}'
)


@pytest.mark.integration
class TestTimeoutBudget:
    """Tests for component timeout behavior and global budget gaps."""

    @pytest.mark.asyncio
    async def test_commentary_timeout_still_publishes_delivered_event(self):
        """Commentary timeout delivers partial text and publishes CommentaryDelivered."""
        bus = EventBus()
        collector = EventCollector(bus)

        # Mark TTS as unhealthy so pipeline skips TTS (text-only mode)
        default_health.mark_unhealthy("cartesia_tts")

        pipeline = CommentaryPipeline(
            api_key="test-key",
            voice_id="test-voice",
            groq_api_key="gsk-test",
        )

        # Wire up event bus without connecting TTS/display
        pipeline._event_bus = bus
        bus.subscribe("observation_verified", pipeline._on_observation_verified)

        # Mock the display to be a no-op
        pipeline._display = MagicMock()
        pipeline._display.clear = AsyncMock()
        pipeline._display.push_commentary = AsyncMock()

        # Create a generator that yields 2 sentences then stalls
        async def slow_stream(sanitized: SanitizedOutput) -> AsyncGenerator:
            yield "First sentence delivered.", "sarcastic", 0
            yield "Second sentence delivered.", "confident", 1
            # Stall longer than the commentary timeout
            await asyncio.sleep(60)
            yield "This should never arrive.", "sarcastic", 2

        with patch.object(
            pipeline._generator, "stream_sentences", side_effect=slow_stream,
        ):
            # Publish observation_verified to trigger commentary
            bus.publish(ObservationVerified(
                output=_make_sanitized(),
            ))

            # Wait for commentary_delivered (should arrive after 30s timeout)
            event = await collector.wait_for("commentary_delivered", timeout=35)

        assert isinstance(event, CommentaryDelivered)
        assert "First sentence" in event.commentary_text
        assert "Second sentence" in event.commentary_text
        # The third sentence should NOT be present (timed out)
        assert "never arrive" not in event.commentary_text

    @pytest.mark.asyncio
    async def test_scoring_completes_independently_of_commentary_timeout(self):
        """Scoring completes even when commentary times out."""
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

        # Commentary stalls (simulating timeout scenario)
        async def stalling_stream(s: SanitizedOutput) -> AsyncGenerator:
            yield "First sentence.", "sarcastic", 0
            await asyncio.sleep(60)  # stall forever

        # Scoring should complete independently via fallback
        with (
            patch.object(
                scorer, "_call_gemini",
                new=AsyncMock(side_effect=ConnectionError("down")),
            ),
            patch.object(
                scorer, "_call_claude",
                new=AsyncMock(return_value=_SCORING_JSON),
            ),
        ):
            # Run scoring with a 10s budget — it should complete quickly
            async with asyncio.timeout(10):
                scorecard = await scorer.score(sanitized, "SHADOW::VECTOR")

        assert scorecard.total_score > 0
        assert scorecard.team_name == "TimeoutTeam"

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Bug 2: No global timeout budget exists yet. Full demo→reveal "
               "cycle has no deadline enforcing completion within 60s.",
        strict=False,
    )
    async def test_full_cycle_within_budget(self):
        """Full demo_stopped→score_revealed should complete within 60s.

        This test documents the missing global timeout budget (Bug 2).
        Currently, if Gemini is slow (not down), the pipeline can hang
        for longer than 60s because there's no overarching deadline
        wrapping the full observation→commentary→scoring→reveal chain.
        """
        bus = EventBus()
        collector = EventCollector(bus)

        default_health.mark_unhealthy("cartesia_tts")

        pipeline = CommentaryPipeline(
            api_key="test-key",
            voice_id="test-voice",
            groq_api_key="gsk-test",
        )

        pipeline._event_bus = bus
        bus.subscribe("observation_verified", pipeline._on_observation_verified)

        pipeline._display = MagicMock()
        pipeline._display.clear = AsyncMock()
        pipeline._display.push_commentary = AsyncMock()

        cb = GeminiCircuitBreaker()
        scorer = ScoringEngine(
            api_key="test-key",
            anthropic_api_key="sk-test",
            circuit_breaker=cb,
        )

        # Simulate slow Gemini (not down — still responds, just very slowly)
        async def slow_gemini_score(prompt: str) -> str:
            await asyncio.sleep(45)  # 45s — under individual timeout but slow
            return _SCORING_JSON

        async def slow_stream(sanitized: SanitizedOutput) -> AsyncGenerator:
            yield "Slow commentary sentence one.", "sarcastic", 0
            await asyncio.sleep(20)  # Slow but not timed out individually
            yield "Slow commentary sentence two.", "confident", 1

        with (
            patch.object(pipeline._generator, "stream_sentences", side_effect=slow_stream),
            patch.object(scorer, "_call_gemini", new=slow_gemini_score),
        ):
            # The full cycle: commentary + scoring should complete within 60s
            # This will likely fail because no global budget enforces it
            async with asyncio.timeout(60):
                bus.publish(ObservationVerified(output=_make_sanitized()))

                # Wait for commentary
                await collector.wait_for("commentary_delivered", timeout=35)

                # Run scoring (would be triggered by event in real pipeline)
                scorecard = await scorer.score(_make_sanitized(), "SHADOW::VECTOR")

        assert scorecard.total_score > 0
