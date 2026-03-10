"""Edge-case tests for circuit breaker, retry interactions, and TTS event bus wiring.

Covers thundering-herd prevention in half-open state, probe lifecycle,
permanent vs transient trip precedence, TTS event bus integration, cancel
semantics, and fallback event publishing.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.event_bus import EventBus
from src.commentary.models import TTSFinished, TTSSpeaking
from src.commentary.pipeline import CommentaryPipeline
from src.commentary.tts_engine import TTSEngine
from src.resilience.circuit_breaker import GeminiCircuitBreaker


# ---------------------------------------------------------------------------
# Circuit breaker edge cases
# ---------------------------------------------------------------------------


class TestHalfOpenProbeGate:
    """Thundering herd prevention: only one caller gets the probe."""

    def test_half_open_probe_gate_only_one_caller(self):
        """Trip breaker, wait past cooldown, call available twice.

        Only the first returns True (probe), the second returns False.
        This tests the thundering herd fix.
        """
        cb = GeminiCircuitBreaker(initial_cooldown=0.05)
        cb.trip()
        time.sleep(0.1)  # past cooldown

        first = cb.available   # should claim the probe slot
        second = cb.available  # should be blocked

        assert first is True
        assert second is False

    def test_probe_in_flight_cleared_after_successful_recovery(self):
        """After trip -> cooldown -> probe succeeds -> record_success,
        a second trip+cooldown cycle allows a new probe.
        """
        cb = GeminiCircuitBreaker(initial_cooldown=0.05)

        # First cycle
        cb.trip()
        time.sleep(0.1)
        assert cb.available is True   # claim probe
        cb.record_success()
        assert cb.state == "closed"

        # Second cycle — a fresh probe should be available
        cb.trip()
        time.sleep(0.1)
        assert cb.available is True   # new probe should work
        assert cb.state == "half_open"

    def test_double_trip_while_open_resets_tripped_at(self):
        """Calling trip() twice while open resets the cooldown timer."""
        cb = GeminiCircuitBreaker(initial_cooldown=0.15)
        cb.trip()
        first_tripped_at = cb._tripped_at

        time.sleep(0.05)
        cb.trip()  # re-trip while still open
        second_tripped_at = cb._tripped_at

        # The second trip should have a later timestamp
        assert second_tripped_at > first_tripped_at

        # Cooldown should be measured from the second trip, so after
        # only 0.05s more (total 0.10s from second trip) we should
        # still be open, not half_open.
        time.sleep(0.05)
        assert cb.state == "open"

    def test_transient_trip_after_permanent_is_ignored(self):
        """trip() after trip_permanent() leaves state unchanged."""
        cb = GeminiCircuitBreaker(initial_cooldown=0.05)
        cb.trip_permanent()

        state_before = cb._state
        permanent_before = cb._permanent
        tripped_at_before = cb._tripped_at

        cb.trip()  # should be a no-op

        assert cb._state == state_before
        assert cb._permanent == permanent_before
        # tripped_at should NOT have been updated by the ignored trip()
        assert cb._tripped_at == tripped_at_before


# ---------------------------------------------------------------------------
# TTS + EventBus integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tts_events_published_to_event_bus():
    """Create a TTSEngine with a real EventBus, mock _send_to_cartesia,
    call speak(), verify TTSSpeaking and TTSFinished events are received.
    """
    bus = EventBus()

    received: list[str] = []

    async def on_speaking(event: TTSSpeaking):
        received.append("speaking")

    async def on_finished(event: TTSFinished):
        received.append("finished")

    bus.subscribe("tts_speaking", on_speaking)
    bus.subscribe("tts_finished", on_finished)

    engine = TTSEngine(api_key="test-key", voice_id="test-voice", event_bus=bus)
    engine._connected = True
    engine._closing = False
    engine._send_to_cartesia = AsyncMock()

    await engine.speak("Hello world", "ctx-1")

    # Drain the event bus so async subscriber tasks complete
    await bus.drain(timeout=2.0)

    assert "speaking" in received
    assert "finished" in received
    # speaking must come before finished
    assert received.index("speaking") < received.index("finished")


@pytest.mark.asyncio
async def test_tts_event_bus_wired_in_commentary_setup():
    """Verify pipeline._tts._event_bus is None before setup()
    and is event_bus after setup().
    """
    pipeline = CommentaryPipeline(
        api_key="test-key",
        voice_id="test-voice",
        groq_api_key="gsk-test",
    )

    # Before setup, TTS event_bus should be None (constructed without bus)
    assert pipeline._tts._event_bus is None

    bus = EventBus()

    # Mock connect and display start to avoid real I/O
    pipeline._tts.connect = AsyncMock()
    pipeline._display.start = AsyncMock()

    await pipeline.setup(bus)

    assert pipeline._tts._event_bus is bus


# ---------------------------------------------------------------------------
# TTS cancel edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tts_fallback_not_invoked_after_cancel():
    """Set _cancelled, trigger Cartesia failure path, verify
    _fallback.speak is NOT called (the bug fix).
    """
    bus = EventBus()
    engine = TTSEngine(api_key="test-key", voice_id="test-voice", event_bus=bus)
    engine._connected = True
    engine._closing = False

    # Make _send_to_cartesia raise so we hit the fallback path
    engine._send_to_cartesia = AsyncMock(side_effect=ConnectionError("boom"))

    # Mock fallback chain
    mock_fallback = MagicMock()
    mock_fallback.available = True
    mock_fallback.speak = AsyncMock()
    engine._fallback = mock_fallback

    # Cancel BEFORE speak — the speak method should bail out before
    # reaching both Cartesia and the fallback.
    engine.cancel()
    await engine.speak("Should not be spoken", "ctx-1")

    engine._send_to_cartesia.assert_not_called()
    mock_fallback.speak.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_is_idempotent():
    """Calling cancel() multiple times with no speak in flight does not raise."""
    engine = TTSEngine(api_key="test-key", voice_id="test-voice")

    # Should not raise on any of these calls
    engine.cancel()
    engine.cancel()
    engine.cancel()

    assert engine._cancelled.is_set()


@pytest.mark.asyncio
async def test_tts_finished_fires_even_on_fallback():
    """When Cartesia fails and fallback is used, TTSFinished is still
    published via the finally block.
    """
    bus = EventBus()

    received: list[str] = []

    async def on_speaking(event: TTSSpeaking):
        received.append("speaking")

    async def on_finished(event: TTSFinished):
        received.append("finished")

    bus.subscribe("tts_speaking", on_speaking)
    bus.subscribe("tts_finished", on_finished)

    engine = TTSEngine(api_key="test-key", voice_id="test-voice", event_bus=bus)
    engine._connected = True
    engine._closing = False

    # Make Cartesia fail so fallback is triggered
    engine._send_to_cartesia = AsyncMock(side_effect=RuntimeError("Cartesia down"))

    # Provide a working fallback
    mock_fallback = MagicMock()
    mock_fallback.available = True
    mock_fallback.speak = AsyncMock()
    engine._fallback = mock_fallback

    await engine.speak("Fallback sentence", "ctx-1")

    # Drain bus so subscriber tasks complete
    await bus.drain(timeout=2.0)

    # Fallback should have been called
    mock_fallback.speak.assert_called_once_with("Fallback sentence")

    # Both events should have fired (speaking before the try, finished in finally)
    assert "speaking" in received
    assert "finished" in received
    assert received.index("speaking") < received.index("finished")
