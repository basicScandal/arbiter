"""Lightweight async event bus for decoupling capture components.

Provides pub/sub functionality using asyncio.create_task() for non-blocking
event delivery. Subscribers receive typed CaptureEvent instances.

Includes backpressure monitoring: tracks in-flight task count and logs
warnings when pending tasks exceed a configurable threshold.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Callable

from src.capture.models import CaptureEvent
from src.resilience.metrics import default_metrics

logger = logging.getLogger(__name__)

BACKPRESSURE_THRESHOLD = 50


class EventBus:
    """Async pub/sub event bus for capture layer events.

    Subscribers are async callables that receive CaptureEvent instances.
    Publishing is non-blocking -- each subscriber callback runs as an
    independent asyncio task. Errors in callbacks are logged but never
    propagate to the publisher, ensuring bus resilience.

    Tracks pending task count for backpressure monitoring. Logs a warning
    and increments a metric when pending tasks exceed BACKPRESSURE_THRESHOLD.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._global_subscribers: list[Callable] = []
        self._pending_count: int = 0
        self._drain_event: asyncio.Event = asyncio.Event()
        self._drain_event.set()  # starts drained (no pending tasks)

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Register a callback for a specific event type.

        Args:
            event_type: The event type string to listen for (e.g., "demo_started").
            callback: An async callable that accepts a CaptureEvent.
        """
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Remove a callback for a specific event type.

        Args:
            event_type: The event type string.
            callback: The callback to remove.
        """
        try:
            self._subscribers[event_type].remove(callback)
        except ValueError:
            pass  # Callback not found, ignore silently

    def subscribe_all(self, callback: Callable) -> None:
        """Register a callback for ALL event types.

        Useful for logging or debugging. The callback receives every event
        published on the bus regardless of event_type.

        Args:
            callback: An async callable that accepts a CaptureEvent.
        """
        self._global_subscribers.append(callback)

    @property
    def pending_count(self) -> int:
        """Number of in-flight subscriber tasks."""
        return self._pending_count

    def publish(self, event: CaptureEvent) -> None:
        """Publish an event to all registered subscribers.

        Each subscriber callback is dispatched as an independent asyncio task
        so publishing never blocks. Errors in callbacks are caught and logged.

        Args:
            event: The CaptureEvent to publish.
        """
        callbacks = list(self._subscribers.get(event.event_type, []))
        callbacks.extend(self._global_subscribers)

        for callback in callbacks:
            self._pending_count += 1
            self._drain_event.clear()
            asyncio.create_task(self._safe_call(callback, event), name=f"bus-{event.event_type}")

        if self._pending_count > BACKPRESSURE_THRESHOLD:
            logger.warning(
                "EventBus backpressure warning: %d pending tasks (threshold=%d)",
                self._pending_count,
                BACKPRESSURE_THRESHOLD,
            )
            default_metrics.inc("eventbus.backpressure_warning")

    async def drain(self, timeout: float = 5.0) -> None:
        """Wait for all pending tasks to complete.

        Args:
            timeout: Maximum seconds to wait. Defaults to 5.0.

        Raises:
            TimeoutError: If pending tasks don't complete within timeout.
        """
        if self._pending_count == 0:
            return
        await asyncio.wait_for(self._drain_event.wait(), timeout=timeout)

    async def _safe_call(self, callback: Callable, event: CaptureEvent) -> None:
        """Call a subscriber callback with error isolation.

        Args:
            callback: The async callable to invoke.
            event: The event to pass to the callback.
        """
        try:
            await callback(event)
        except Exception:
            logger.exception(
                "Error in event bus callback %s for event type '%s'",
                callback.__name__ if hasattr(callback, "__name__") else str(callback),
                event.event_type,
            )
        finally:
            self._pending_count -= 1
            if self._pending_count == 0:
                self._drain_event.set()


# Module-level singleton for convenience
default_bus = EventBus()
