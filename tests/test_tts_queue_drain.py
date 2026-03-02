"""Tests for TTS queue drain on demo transition.

Validates that TTSEngine.cancel() stops pending speak() calls and
that the CommentaryPipeline cancels TTS when a new demo starts.

Phase 1, Item 4 of the real-world testing strategy.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

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
async def test_cancel_resets_on_explicit_clear():
    """After cancel(), flag persists until explicitly cleared (by pipeline).

    The flag is no longer auto-cleared by speak() — pipeline._on_observation_verified()
    clears it when the new demo's commentary starts.
    """
    engine = TTSEngine(api_key="test-key", voice_id="test-voice")

    send_mock = AsyncMock()
    engine._send_to_cartesia = send_mock
    engine._connected = True
    engine._closing = False

    # Cancel, then call speak twice — both should be skipped
    engine.cancel()
    await engine.speak("This is cancelled.", "ctx-1")
    await engine.speak("This is also cancelled.", "ctx-2")
    send_mock.assert_not_called()

    # Simulate what pipeline._on_observation_verified() does: clear the flag
    engine._cancelled.clear()

    # Now speak should work
    await engine.speak("This should work.", "ctx-3")
    send_mock.assert_called_once()


@pytest.mark.asyncio
async def test_demo_started_cancels_tts():
    """Pipeline._on_demo_started() calls tts.cancel() before playing chime.

    The cancel flag is NOT cleared here — it persists so all queued old
    speaks see it. It's only cleared at the start of _on_observation_verified
    when the new demo's commentary begins.
    """
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
async def test_overlapping_demo_no_audio_bleed():
    """Start commentary delivery, publish demo_started mid-delivery,
    assert remaining sentences are not spoken.

    Bug 4 fix: cancel() now sets a persistent flag checked in both
    the pre-lock path AND inside _send_to_cartesia's receive loop.
    Pipeline._on_demo_started() clears the flag after cancel so new
    speaks for the next demo work normally.
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
    tts = pipeline._tts

    async def tracking_speak(sentence, context_id, emotion="sarcastic", is_continuation=False):
        """Track which sentences are spoken, checking cancel flag like real speak()."""
        if tts._cancelled.is_set():
            return
        await asyncio.sleep(0.1)  # simulate TTS time
        spoken_sentences.append(sentence)

    # Replace TTS methods but keep the real cancel flag
    tts.speak = tracking_speak
    tts.play_sound = AsyncMock()
    tts._closing = False

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
            await tts.speak(sentence, context_id, is_continuation=(i > 0))

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


@pytest.mark.asyncio
async def test_cancel_stops_mid_stream_cartesia():
    """_send_to_cartesia breaks out of the receive loop when _cancelled is set."""
    engine = TTSEngine(api_key="test-key", voice_id="test-voice")
    engine._connected = True
    engine._closing = False

    chunks_played: list[bytes] = []

    # Simulate a Cartesia context that yields 10 audio chunks
    class FakeEvent:
        def __init__(self, index: int):
            self.type = "chunk"
            self.audio = f"audio-{index}".encode()

    class FakeContext:
        async def send(self, **kwargs):
            pass

        async def no_more_inputs(self):
            pass

        async def receive(self):
            for i in range(10):
                await asyncio.sleep(0.05)
                yield FakeEvent(i)

        def __init__(self):
            pass

    class FakeConnection:
        def context(self, **kwargs):
            return FakeContext()

    engine._connection = FakeConnection()

    # Mock audio processor and stream
    engine._audio_processor = MagicMock()
    engine._audio_processor.process_chunk.side_effect = lambda x: x
    mock_stream = MagicMock()
    mock_stream.write = MagicMock()  # synchronous mock for to_thread
    engine._stream = mock_stream

    # Start _send_to_cartesia in background, cancel after 2 chunks
    async def cancel_after_delay():
        await asyncio.sleep(0.15)  # ~3 chunks at 0.05s each
        engine.cancel()

    cancel_task = asyncio.create_task(cancel_after_delay())

    await engine._send_to_cartesia("Test sentence", "ctx-1", "sarcastic", False)
    await cancel_task

    # Should have played some chunks but NOT all 10
    played_count = mock_stream.write.call_count
    assert played_count < 10, f"Expected <10 chunks but got {played_count}"
    assert played_count > 0, "Expected at least 1 chunk to be played"


@pytest.mark.asyncio
async def test_multiple_queued_speaks_all_cancelled():
    """Queue 3 speaks, cancel before first starts, verify none call _send_to_cartesia."""
    engine = TTSEngine(api_key="test-key", voice_id="test-voice")

    send_mock = AsyncMock()
    engine._send_to_cartesia = send_mock
    engine._connected = True
    engine._closing = False

    # Cancel before any speak starts
    engine.cancel()

    # All 3 should be cancelled by the persistent flag
    await engine.speak("First", "ctx-1")
    await engine.speak("Second", "ctx-2")
    await engine.speak("Third", "ctx-3")

    send_mock.assert_not_called()

    # Verify flag is still set (not cleared by any speak)
    assert engine._cancelled.is_set()
