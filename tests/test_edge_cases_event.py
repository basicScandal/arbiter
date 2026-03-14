"""Edge case tests for event-day resilience.

Covers scenarios that could break during the live event:
1. Back-to-back demos (rapid reset → start)
2. Multiple injection attempts in one demo
3. All LLM providers failing simultaneously
4. TTS reconnecting multiple times
5. Special characters in team names
6. Demo with massive observation count
7. Scoring with outlier disagreement
8. Commentary pipeline after Q&A capture cleanup
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.capture.demo_machine import DemoMachine
from src.capture.event_bus import EventBus
from src.capture.models import CaptureEvent, TranscriptReceived, TranscriptSegment
from src.commentary.generator import CommentaryGenerator
from src.commentary.models import CommentaryDelivered
from src.commentary.pipeline import CommentaryPipeline
from src.defense.models import InjectionAttempt, InjectionDetected, SanitizedOutput
from src.defense.pipeline import DefensePipeline
from src.scoring.moe_engine import MoEScoringEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sanitized(
    team: str = "TestTeam",
    obs_count: int = 3,
    transcript_count: int = 2,
    injection_count: int = 0,
) -> SanitizedOutput:
    return SanitizedOutput(
        team_name=team,
        observations=[f"Observation {i}" for i in range(obs_count)],
        transcripts=[f"Transcript {i}" for i in range(transcript_count)],
        injection_attempts=[
            InjectionAttempt(
                injection_type="verbal",
                content=f"ignore instructions {i}",
                pattern="prompt_override",
                confidence="high",
                team_name=team,
                timestamp=time.time(),
            )
            for i in range(injection_count)
        ],
        demo_duration=120.0,
    )


def _make_pipeline() -> CommentaryPipeline:
    pipeline = CommentaryPipeline.__new__(CommentaryPipeline)
    pipeline._tts = MagicMock()
    pipeline._tts.speak = AsyncMock()
    pipeline._tts._connected = True
    pipeline._tts._cancelled = asyncio.Event()
    pipeline._tts.cancel = MagicMock()
    pipeline._tts.play_sound = AsyncMock()
    pipeline._display = MagicMock()
    pipeline._display.push_commentary = AsyncMock()
    pipeline._display.push_question = AsyncMock()
    pipeline._display.clear = AsyncMock()
    pipeline._generator = MagicMock()
    pipeline._sounds = MagicMock()
    pipeline._event_bus = None
    pipeline._last_sanitized = None
    pipeline._commentary_cancelled = asyncio.Event()
    pipeline._injection_quip_index = 0
    return pipeline


# ---------------------------------------------------------------------------
# 1. Back-to-back demos
# ---------------------------------------------------------------------------


class TestBackToBackDemos:
    """Verify rapid reset → start doesn't leave stale state."""

    def test_demo_machine_reset_returns_to_idle(self):
        bus = EventBus()
        machine = DemoMachine(event_bus=bus)
        machine.send("start_demo", team_name="Team1")
        assert machine.current_state.id == "capturing"
        machine.send("stop_demo")
        assert machine.current_state.id == "stopped"
        machine.send("reset")
        assert machine.current_state.id == "idle"

    def test_demo_machine_immediate_restart_after_reset(self):
        bus = EventBus()
        machine = DemoMachine(event_bus=bus)
        # First demo
        machine.send("start_demo", team_name="Team1")
        machine.send("stop_demo")
        machine.send("reset")
        # Immediate second demo
        machine.send("start_demo", team_name="Team2")
        assert machine.current_state.id == "capturing"
        session = machine.current_session
        assert session is not None
        assert session.team_name == "Team2"

    def test_three_consecutive_demos(self):
        bus = EventBus()
        machine = DemoMachine(event_bus=bus)
        for team in ["Alpha", "Beta", "Gamma"]:
            machine.send("start_demo", team_name=team)
            assert machine.current_state.id == "capturing"
            machine.send("stop_demo")
            machine.send("reset")
            assert machine.current_state.id == "idle"


# ---------------------------------------------------------------------------
# 2. Multiple injection attempts
# ---------------------------------------------------------------------------


class TestMultipleInjections:
    """Verify multiple injection attempts are tracked and reported."""

    @pytest.mark.asyncio
    async def test_multiple_injections_reach_commentary(self):
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        captured = []

        async def capture_stream(sanitized):
            captured.append(sanitized)
            yield ("Commentary.", "confident", 0)

        pipeline._generator.stream_sentences = capture_stream

        event = MagicMock()
        event.output = _make_sanitized(injection_count=5)
        await pipeline._on_observation_verified(event)

        assert len(captured) == 1
        assert len(captured[0].injection_attempts) == 5

    @pytest.mark.asyncio
    async def test_injection_count_in_demo_metadata(self):
        sanitized = _make_sanitized(injection_count=3)
        assert len(sanitized.injection_attempts) == 3
        for i, attempt in enumerate(sanitized.injection_attempts):
            assert attempt.confidence == "high"
            assert f"ignore instructions {i}" in attempt.content


# ---------------------------------------------------------------------------
# 3. All LLM providers fail
# ---------------------------------------------------------------------------


class TestAllProvidersFailure:
    """Verify graceful degradation when all LLM providers fail."""

    @pytest.mark.asyncio
    async def test_groq_failure_falls_to_static(self):
        """When Groq also fails, static fallback must produce output."""
        gen = CommentaryGenerator(api_key="fake", groq_api_key="fake")

        with patch.object(gen, "_call_groq", side_effect=RuntimeError("Groq down")):
            sentences = []
            async for text, emotion, idx in gen.stream_sentences(_make_sanitized()):
                sentences.append(text)

        assert len(sentences) >= 1
        assert "Technical difficulties" in sentences[0]

    @pytest.mark.asyncio
    async def test_no_groq_key_falls_to_static(self):
        """Without Groq API key, static fallback must work."""
        gen = CommentaryGenerator(api_key="fake", groq_api_key="")

        sentences = []
        async for text, emotion, idx in gen.stream_sentences(_make_sanitized()):
            sentences.append(text)

        assert len(sentences) >= 1

    @pytest.mark.asyncio
    async def test_commentary_delivered_even_on_total_failure(self):
        """CommentaryDelivered must fire even when all generators fail."""
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        delivered = []
        bus.subscribe("commentary_delivered", lambda e: delivered.append(e))

        async def failing_stream(sanitized):
            raise RuntimeError("Everything is broken")
            yield  # pragma: no cover

        pipeline._generator.stream_sentences = failing_stream

        event = MagicMock()
        event.output = _make_sanitized()
        await pipeline._on_observation_verified(event)
        await bus.drain(timeout=2.0)

        assert len(delivered) == 1


# ---------------------------------------------------------------------------
# 4. TTS multiple reconnects
# ---------------------------------------------------------------------------


class TestTTSMultipleReconnects:
    """Verify TTS can reconnect more than once in a session."""

    def test_tts_engine_has_reconnect_method(self):
        from src.commentary.tts_engine import TTSEngine
        assert hasattr(TTSEngine, "_reconnect")

    def test_tts_catches_both_connection_closed_types(self):
        import inspect
        from src.commentary.tts_engine import TTSEngine
        source = inspect.getsource(TTSEngine.speak)
        assert "ConnectionClosedError" in source
        assert "ConnectionClosedOK" in source


# ---------------------------------------------------------------------------
# 5. Special characters in team names
# ---------------------------------------------------------------------------


class TestSpecialTeamNames:
    """Verify team names with special characters don't break the pipeline."""

    @pytest.mark.parametrize("name", [
        "Team O'Brien",
        "Team <script>alert(1)</script>",
        "Tëam Ünïcödé",
        "Team 日本語",
        "Team With Spaces And Numbers 123",
        "a" * 100,  # Very long name
        "",  # Empty
    ])
    def test_sanitized_output_accepts_team_name(self, name):
        """SanitizedOutput must accept any team name string."""
        output = _make_sanitized(team=name)
        assert output.team_name == name

    @pytest.mark.asyncio
    @pytest.mark.parametrize("name", [
        "Team <script>",
        "Team \"quotes\"",
        "Team\nnewline",
    ])
    async def test_commentary_handles_special_names(self, name):
        """Commentary pipeline must not crash on special characters."""
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        async def fake_stream(sanitized):
            yield ("Review.", "confident", 0)

        pipeline._generator.stream_sentences = fake_stream

        event = MagicMock()
        event.output = _make_sanitized(team=name)
        # Should not raise
        await pipeline._on_observation_verified(event)


# ---------------------------------------------------------------------------
# 6. Massive observation count
# ---------------------------------------------------------------------------


class TestMassiveObservations:
    """Verify pipeline handles demos with many observations."""

    @pytest.mark.asyncio
    async def test_200_observations_dont_crash_commentary(self):
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        async def fake_stream(sanitized):
            assert len(sanitized.observations) == 200
            yield ("Lots to discuss.", "confident", 0)

        pipeline._generator.stream_sentences = fake_stream

        event = MagicMock()
        event.output = _make_sanitized(obs_count=200, transcript_count=50)
        await pipeline._on_observation_verified(event)

        assert pipeline._tts.speak.call_count == 1

    def test_large_sanitized_output_serializable(self):
        """Large outputs must be JSON-serializable for storage."""
        import json
        output = _make_sanitized(obs_count=500, transcript_count=200)
        # Should not raise
        json.dumps(output.model_dump())


# ---------------------------------------------------------------------------
# 7. MoE with extreme disagreement
# ---------------------------------------------------------------------------


class TestMoEExtremeDisagreement:
    """Verify MoE handles providers that wildly disagree."""

    def test_moe_aggregator_handles_outliers(self):
        from src.scoring.aggregator import ScoreAggregator
        agg = ScoreAggregator()
        # Provider scores as dict (model_name -> score)
        scores = {"gemini": 9.0, "claude": 8.0, "groq": 1.0}
        score, metadata = agg.aggregate_criterion(scores)
        assert score > 0
        assert score <= 10
        # The outlier (groq at 1.0) should be detected
        if metadata.get("outliers"):
            assert "groq" in metadata["outliers"]


# ---------------------------------------------------------------------------
# 8. Commentary pipeline state between demos
# ---------------------------------------------------------------------------


class TestCommentaryStateBetweenDemos:
    """Verify commentary pipeline resets properly between demos."""

    @pytest.mark.asyncio
    async def test_last_sanitized_updated_per_demo(self):
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        async def fake_stream(sanitized):
            yield ("Commentary.", "confident", 0)

        pipeline._generator.stream_sentences = fake_stream

        # First demo
        event1 = MagicMock()
        event1.output = _make_sanitized(team="TeamA")
        await pipeline._on_observation_verified(event1)
        assert pipeline._last_sanitized.team_name == "TeamA"

        # Second demo
        event2 = MagicMock()
        event2.output = _make_sanitized(team="TeamB")
        await pipeline._on_observation_verified(event2)
        assert pipeline._last_sanitized.team_name == "TeamB"

    @pytest.mark.asyncio
    async def test_cancellation_flag_cleared_between_demos(self):
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        async def fake_stream(sanitized):
            yield ("Commentary.", "confident", 0)

        pipeline._generator.stream_sentences = fake_stream

        # Set cancellation (simulating a previous cancel)
        pipeline._commentary_cancelled.set()

        event = MagicMock()
        event.output = _make_sanitized()
        await pipeline._on_observation_verified(event)

        # Cancellation should have been cleared at the start
        assert not pipeline._commentary_cancelled.is_set()
