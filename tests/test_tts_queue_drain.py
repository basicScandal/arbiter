"""Tests for TTS queue drain on demo transition.

Validates that TTSEngine.cancel() stops pending speak() calls and
that the CommentaryPipeline cancels TTS when a new demo starts.

Phase 1, Item 4 of the real-world testing strategy.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.event_bus import EventBus
from src.capture.models import DemoStarted
from src.commentary.pipeline import CommentaryPipeline
from src.commentary.tts_engine import TTSEngine


@pytest.mark.asyncio
async def test_cancel_stops_pending_speak():
    """After cancel(), a pending speak() returns early without speaking."""
    engine = TTSEngine(api_key="test-key", voice_id="test-voice")

    # Track whether _send_to_cartesia would be called
    send_mock = AsyncMock()
    engine._send_to_cartesia = send_mock
    engine._connected = True
    engine._closing = False

    # Cancel before speaking
    engine.cancel()
    await engine.speak("This should not be spoken.", "ctx-1")

    send_mock.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_resets_on_next_speak():
    """After cancel(), the next speak() call clears the flag and works normally."""
    engine = TTSEngine(api_key="test-key", voice_id="test-voice")

    send_mock = AsyncMock()
    engine._send_to_cartesia = send_mock
    engine._connected = True
    engine._closing = False

    # Cancel, then call speak twice
    engine.cancel()
    await engine.speak("This is cancelled.", "ctx-1")
    send_mock.assert_not_called()

    # Second speak should work — cancel flag was cleared by first speak
    await engine.speak("This should work.", "ctx-2")
    send_mock.assert_called_once()


@pytest.mark.asyncio
async def test_demo_started_cancels_tts():
    """Pipeline._on_demo_started() calls tts.cancel() before playing chime."""
    pipeline = CommentaryPipeline(
        api_key="test-key",
        voice_id="test-voice",
        groq_api_key="gsk-test",
    )

    # Replace TTS with a mock to track cancel() calls
    mock_tts = MagicMock()
    mock_tts.cancel = MagicMock()
    mock_tts.play_sound = AsyncMock()
    pipeline._tts = mock_tts

    event = DemoStarted(team_name="TeamB")
    await pipeline._on_demo_started(event)

    mock_tts.cancel.assert_called_once()
    mock_tts.play_sound.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Bug 4: TTS cancel prevents new speak() calls but cannot stop "
           "audio that is already being written to PyAudio. Full audio bleed "
           "prevention requires cancelling the in-flight Cartesia stream.",
    strict=False,
)
async def test_overlapping_demo_no_audio_bleed():
    """Start commentary delivery, publish demo_started mid-delivery,
    assert remaining sentences are not spoken.

    This xfail documents that while cancel() prevents NEW speak() calls,
    a sentence already being spoken (audio already streaming to PyAudio)
    will finish playing. Full prevention of audio bleed requires
    interrupting the in-flight Cartesia WebSocket stream.
    """
    bus = EventBus()
    pipeline = CommentaryPipeline(
        api_key="test-key",
        voice_id="test-voice",
        groq_api_key="gsk-test",
    )
    pipeline._event_bus = bus
    bus.subscribe("demo_started", pipeline._on_demo_started)

    spoken_sentences: list[str] = []

    async def tracking_speak(sentence, context_id, emotion="sarcastic", is_continuation=False):
        """Track which sentences are spoken, with a delay to simulate real TTS."""
        await asyncio.sleep(0.1)  # simulate TTS time
        spoken_sentences.append(sentence)

    # Replace TTS methods
    pipeline._tts.speak = tracking_speak
    pipeline._tts.play_sound = AsyncMock()
    pipeline._tts._closing = False

    # Start speaking 5 sentences in background
    async def speak_all():
        context_id = "test-ctx"
        for i, sentence in enumerate([
            "Sentence one from Team A.",
            "Sentence two from Team A.",
            "Sentence three from Team A.",
            "Sentence four from Team A.",
            "Sentence five from Team A.",
        ]):
            await pipeline._tts.speak(sentence, context_id, is_continuation=(i > 0))

    speak_task = asyncio.create_task(speak_all())

    # Let 2 sentences through, then start Team B's demo
    await asyncio.sleep(0.25)
    bus.publish(DemoStarted(team_name="TeamB"))

    # Wait for background speak to finish
    await asyncio.sleep(1.0)
    speak_task.cancel()
    try:
        await speak_task
    except asyncio.CancelledError:
        pass

    # With perfect cancel, only 2-3 sentences should have been spoken
    # (the cancel happens after ~0.25s, and each sentence takes ~0.1s)
    assert len(spoken_sentences) <= 3, (
        f"Expected at most 3 sentences but got {len(spoken_sentences)}: {spoken_sentences}"
    )
