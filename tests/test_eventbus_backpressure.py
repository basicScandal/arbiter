"""Tests for EventBus backpressure monitoring.

Validates that the EventBus tracks in-flight tasks, warns on threshold
breach, drains cleanly, and handles errors without leaking the counter.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from src.capture.event_bus import BACKPRESSURE_THRESHOLD, EventBus
from src.capture.models import CaptureEvent
from src.resilience.metrics import default_metrics


@pytest.mark.asyncio
async def test_pending_count_tracks_inflight_tasks():
    """Pending count increments on publish and returns to 0 after drain."""
    bus = EventBus()
    done = asyncio.Event()

    async def slow_handler(event: CaptureEvent) -> None:
        await done.wait()

    bus.subscribe("test", slow_handler)
    bus.publish(CaptureEvent(event_type="test"))

    # Task is in flight — pending count should be > 0
    assert bus.pending_count > 0

    # Release the handler and drain
    done.set()
    await bus.drain(timeout=2.0)
    assert bus.pending_count == 0


@pytest.mark.asyncio
async def test_backpressure_warning_logged_at_threshold(caplog):
    """Warning is logged and metric incremented when pending > threshold."""
    bus = EventBus()
    hold = asyncio.Event()

    async def blocking_handler(event: CaptureEvent) -> None:
        await hold.wait()

    bus.subscribe("burst", blocking_handler)

    with caplog.at_level(logging.WARNING):
        for _ in range(BACKPRESSURE_THRESHOLD + 1):
            bus.publish(CaptureEvent(event_type="burst"))

    assert bus.pending_count == BACKPRESSURE_THRESHOLD + 1
    assert "backpressure warning" in caplog.text.lower()
    assert default_metrics.get_counters().get("eventbus.backpressure_warning", 0) > 0

    # Cleanup
    hold.set()
    await bus.drain(timeout=5.0)


@pytest.mark.asyncio
async def test_drain_waits_for_completion():
    """drain() blocks until all in-flight handlers finish."""
    bus = EventBus()
    results: list[int] = []

    async def slow_handler(event: CaptureEvent) -> None:
        await asyncio.sleep(0.05)
        results.append(1)

    bus.subscribe("work", slow_handler)

    for _ in range(5):
        bus.publish(CaptureEvent(event_type="work"))

    await bus.drain(timeout=5.0)
    assert len(results) == 5
    assert bus.pending_count == 0


@pytest.mark.asyncio
async def test_drain_timeout_raises():
    """drain() raises TimeoutError when tasks don't complete in time."""
    bus = EventBus()

    async def forever_handler(event: CaptureEvent) -> None:
        await asyncio.sleep(100)

    bus.subscribe("stuck", forever_handler)
    bus.publish(CaptureEvent(event_type="stuck"))

    with pytest.raises(TimeoutError):
        await bus.drain(timeout=0.01)


@pytest.mark.asyncio
async def test_error_in_callback_still_decrements_pending():
    """Pending count returns to 0 even when a handler raises."""
    bus = EventBus()

    async def bad_handler(event: CaptureEvent) -> None:
        raise RuntimeError("boom")

    bus.subscribe("fail", bad_handler)
    bus.publish(CaptureEvent(event_type="fail"))

    await bus.drain(timeout=2.0)
    assert bus.pending_count == 0
