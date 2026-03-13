"""Integration tests for full multi-sentence commentary delivery.

Validates that the commentary pipeline delivers ALL sentences, not just the first
one. Created after a live event incident where commentary was cut off to ~3 seconds
because the Gemini Live session failed silently, leaving 0 observations for the
commentary generator which produced only 1 generic sentence.

These tests exercise the real CommentaryPipeline._on_observation_verified handler
with mocked LLM + TTS, verifying:
1. Multiple sentences are generated and delivered
2. TTS speak() is called for each sentence
3. Display push_commentary() is called for each sentence
4. CommentaryDelivered event fires with the full text
5. Cancellation mid-stream still delivers partial sentences
"""

from __future__ import annotations

import asyncio
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.event_bus import EventBus
from src.commentary.models import CommentaryDelivered
from src.commentary.pipeline import CommentaryPipeline
from src.defense.models import SanitizedOutput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sanitized(
    team_name: str = "TestTeam",
    observations: list[str] | None = None,
    transcripts: list[str] | None = None,
) -> SanitizedOutput:
    return SanitizedOutput(
        team_name=team_name,
        observations=observations or [
            "Team built a neural network-powered port scanner",
            "The tool uses graph analysis to identify lateral movement paths",
            "Demo showed real-time vulnerability correlation",
        ],
        transcripts=transcripts or [
            "We built this in 48 hours using PyTorch",
            "The key insight was modeling network topology as a graph",
        ],
        injection_attempts=[],
        demo_duration=180.0,
    )


_MULTI_SENTENCE_COMMENTARY = [
    ("An impressive display of network analysis.", "confident", 0),
    ("The graph-based approach to lateral movement is genuinely clever.", "impressed", 1),
    ("That said, the vulnerability correlation could use more edge case handling.", "analytical", 2),
    ("Overall, a solid hackathon entry that shows real security thinking.", "content", 3),
]


def _make_pipeline() -> CommentaryPipeline:
    """Create a CommentaryPipeline with fully mocked internals."""
    pipeline = CommentaryPipeline.__new__(CommentaryPipeline)

    # Mock TTS engine
    pipeline._tts = MagicMock()
    pipeline._tts.speak = AsyncMock()
    pipeline._tts._connected = True
    pipeline._tts._cancelled = asyncio.Event()
    pipeline._tts.cancel = MagicMock()
    pipeline._tts.play_sound = AsyncMock()

    # Mock display server
    pipeline._display = MagicMock()
    pipeline._display.push_commentary = AsyncMock()
    pipeline._display.clear = AsyncMock()
    pipeline._display.push_question = AsyncMock()

    # Mock generator
    pipeline._generator = MagicMock()

    # Mock sounds
    pipeline._sounds = MagicMock()
    pipeline._sounds.score_sting = b"fake-audio"

    # Pipeline state
    pipeline._event_bus = None
    pipeline._last_sanitized = None
    pipeline._commentary_cancelled = asyncio.Event()
    pipeline._injection_quip_index = 0

    return pipeline


# ---------------------------------------------------------------------------
# Tests: Full multi-sentence delivery
# ---------------------------------------------------------------------------


class TestFullCommentaryDelivery:
    """Verify the complete commentary delivery chain produces multiple sentences."""

    @pytest.mark.asyncio
    async def test_all_sentences_delivered_to_tts(self):
        """Every sentence from the generator must be spoken via TTS."""
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        async def fake_stream(sanitized):
            for item in _MULTI_SENTENCE_COMMENTARY:
                yield item

        pipeline._generator.stream_sentences = fake_stream

        sanitized = _make_sanitized()
        event = MagicMock()
        event.output = sanitized

        await pipeline._on_observation_verified(event)

        assert pipeline._tts.speak.call_count == 4, (
            f"Expected 4 TTS speak calls, got {pipeline._tts.speak.call_count}"
        )

    @pytest.mark.asyncio
    async def test_all_sentences_pushed_to_display(self):
        """Every sentence must be pushed to the audience display."""
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        async def fake_stream(sanitized):
            for item in _MULTI_SENTENCE_COMMENTARY:
                yield item

        pipeline._generator.stream_sentences = fake_stream

        event = MagicMock()
        event.output = _make_sanitized()

        await pipeline._on_observation_verified(event)

        assert pipeline._display.push_commentary.call_count == 4, (
            f"Expected 4 display pushes, got {pipeline._display.push_commentary.call_count}"
        )

    @pytest.mark.asyncio
    async def test_commentary_delivered_event_contains_full_text(self):
        """CommentaryDelivered event must contain ALL sentences joined."""
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        delivered_events: list[CommentaryDelivered] = []
        bus.subscribe("commentary_delivered", lambda e: delivered_events.append(e))

        async def fake_stream(sanitized):
            for item in _MULTI_SENTENCE_COMMENTARY:
                yield item

        pipeline._generator.stream_sentences = fake_stream

        event = MagicMock()
        event.output = _make_sanitized()

        await pipeline._on_observation_verified(event)
        await bus.drain(timeout=2.0)

        assert len(delivered_events) == 1
        text = delivered_events[0].commentary_text
        assert "impressive display" in text
        assert "genuinely clever" in text
        assert "edge case handling" in text
        assert "solid hackathon entry" in text

    @pytest.mark.asyncio
    async def test_sentence_indices_are_sequential(self):
        """Display pushes must include sequential sentence_index values."""
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        async def fake_stream(sanitized):
            for item in _MULTI_SENTENCE_COMMENTARY:
                yield item

        pipeline._generator.stream_sentences = fake_stream

        event = MagicMock()
        event.output = _make_sanitized()

        await pipeline._on_observation_verified(event)

        indices = [
            call.kwargs.get("sentence_index", call.args[3] if len(call.args) > 3 else None)
            for call in pipeline._display.push_commentary.call_args_list
        ]
        # push_commentary is called with keyword args
        actual_indices = []
        for c in pipeline._display.push_commentary.call_args_list:
            # push_commentary(sentence, team_name, emotion=..., sentence_index=...)
            actual_indices.append(c.kwargs.get("sentence_index", -1))

        assert actual_indices == [0, 1, 2, 3], (
            f"Expected sequential indices [0,1,2,3], got {actual_indices}"
        )

    @pytest.mark.asyncio
    async def test_tts_continuation_flag_set_after_first(self):
        """First sentence should not be continuation, rest should be."""
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        async def fake_stream(sanitized):
            for item in _MULTI_SENTENCE_COMMENTARY:
                yield item

        pipeline._generator.stream_sentences = fake_stream

        event = MagicMock()
        event.output = _make_sanitized()

        await pipeline._on_observation_verified(event)

        speak_calls = pipeline._tts.speak.call_args_list
        # First call: is_continuation=False
        assert speak_calls[0].kwargs.get("is_continuation") is False or \
               (len(speak_calls[0].args) > 3 and speak_calls[0].args[3] is False), \
            "First sentence should not be a continuation"
        # Subsequent calls: is_continuation=True
        for i, c in enumerate(speak_calls[1:], start=1):
            is_cont = c.kwargs.get("is_continuation", c.args[3] if len(c.args) > 3 else None)
            assert is_cont is True, f"Sentence {i} should be a continuation"


class TestCommentaryDeliveryEdgeCases:
    """Edge cases: cancellation, empty observations, single sentence."""

    @pytest.mark.asyncio
    async def test_cancellation_delivers_partial_sentences(self):
        """If cancelled mid-stream, partial sentences still end up in CommentaryDelivered."""
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        delivered_events: list[CommentaryDelivered] = []
        bus.subscribe("commentary_delivered", lambda e: delivered_events.append(e))

        async def fake_stream_with_cancel(sanitized):
            yield ("First sentence delivered.", "confident", 0)
            yield ("Second sentence delivered.", "analytical", 1)
            # Simulate cancellation after 2 sentences
            pipeline._commentary_cancelled.set()
            yield ("This should be skipped.", "neutral", 2)

        pipeline._generator.stream_sentences = fake_stream_with_cancel

        event = MagicMock()
        event.output = _make_sanitized()

        await pipeline._on_observation_verified(event)
        await bus.drain(timeout=2.0)

        # Should have delivered 2 sentences, not 3
        assert pipeline._tts.speak.call_count == 2
        assert len(delivered_events) == 1
        assert "First sentence" in delivered_events[0].commentary_text
        assert "Second sentence" in delivered_events[0].commentary_text
        assert "skipped" not in delivered_events[0].commentary_text

    @pytest.mark.asyncio
    async def test_zero_observations_still_delivers_event(self):
        """Even with no observations, CommentaryDelivered must fire (scoring depends on it)."""
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        delivered_events: list[CommentaryDelivered] = []
        bus.subscribe("commentary_delivered", lambda e: delivered_events.append(e))

        async def fake_stream(sanitized):
            yield ("Not much to work with here.", "neutral", 0)

        pipeline._generator.stream_sentences = fake_stream

        event = MagicMock()
        event.output = _make_sanitized(observations=[], transcripts=[])

        await pipeline._on_observation_verified(event)
        await bus.drain(timeout=2.0)

        assert len(delivered_events) == 1, "CommentaryDelivered must always fire"

    @pytest.mark.asyncio
    async def test_generator_exception_still_fires_delivered_event(self):
        """If the generator crashes, CommentaryDelivered must still fire."""
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        delivered_events: list[CommentaryDelivered] = []
        bus.subscribe("commentary_delivered", lambda e: delivered_events.append(e))

        async def failing_stream(sanitized):
            yield ("One sentence before crash.", "confident", 0)
            raise RuntimeError("LLM connection reset")

        pipeline._generator.stream_sentences = failing_stream

        event = MagicMock()
        event.output = _make_sanitized()

        await pipeline._on_observation_verified(event)
        await bus.drain(timeout=2.0)

        # Must still fire even after crash
        assert len(delivered_events) == 1
        assert "One sentence" in delivered_events[0].commentary_text

    @pytest.mark.asyncio
    async def test_tts_failure_still_pushes_to_display(self):
        """If TTS fails, sentences must still be pushed to the display."""
        pipeline = _make_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        pipeline._tts.speak = AsyncMock(side_effect=Exception("TTS connection lost"))

        async def fake_stream(sanitized):
            for item in _MULTI_SENTENCE_COMMENTARY:
                yield item

        pipeline._generator.stream_sentences = fake_stream

        event = MagicMock()
        event.output = _make_sanitized()

        await pipeline._on_observation_verified(event)

        # Display should still get all sentences even though TTS failed
        assert pipeline._display.push_commentary.call_count >= 4, (
            f"Display should get all sentences despite TTS failure, got {pipeline._display.push_commentary.call_count}"
        )
