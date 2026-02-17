"""Deterministic async event collector for test assertions.

Provides EventCollector, a test helper that subscribes to all events on an
EventBus and allows deterministic waiting for specific event types without
relying on asyncio.sleep() polling.
"""

from __future__ import annotations

import asyncio

from src.capture.models import CaptureEvent
from src.capture.event_bus import EventBus


class EventCollector:
    """Collects events from an EventBus for deterministic test assertions.

    Subscribes to all events via subscribe_all and provides wait_for() to
    deterministically await a specific event type with a timeout, eliminating
    flaky sleep-based polling in async tests.

    Args:
        event_bus: The EventBus instance to subscribe to.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self.events: list[CaptureEvent] = []
        self._waiters: dict[str, asyncio.Event] = {}
        event_bus.subscribe_all(self._on_event)

    async def _on_event(self, event: CaptureEvent) -> None:
        """Handle an incoming event: store it and signal any waiters."""
        self.events.append(event)
        waiter = self._waiters.get(event.event_type)
        if waiter is not None:
            waiter.set()

    async def wait_for(self, event_type: str, timeout: float = 5.0) -> CaptureEvent:
        """Wait for an event of the given type to be captured.

        If an event of the requested type has already been captured, returns
        immediately. Otherwise, registers a waiter and blocks until the event
        arrives or the timeout expires.

        Args:
            event_type: The event type string to wait for.
            timeout: Maximum seconds to wait. Defaults to 5.0.

        Returns:
            The most recent CaptureEvent of the requested type.

        Raises:
            TimeoutError: If no event of the type arrives within the timeout.
        """
        # Check if already captured
        existing = self.of_type(event_type)
        if existing:
            return existing[-1]

        # Register a waiter
        waiter = asyncio.Event()
        self._waiters[event_type] = waiter
        try:
            await asyncio.wait_for(waiter.wait(), timeout=timeout)
        finally:
            self._waiters.pop(event_type, None)

        # Return the last event of the requested type
        matches = self.of_type(event_type)
        if not matches:
            raise TimeoutError(f"No event of type '{event_type}' captured")
        return matches[-1]

    def of_type(self, event_type: str) -> list[CaptureEvent]:
        """Return all captured events matching the given type.

        Args:
            event_type: The event type string to filter by.

        Returns:
            List of matching CaptureEvent instances, in capture order.
        """
        return [e for e in self.events if e.event_type == event_type]

    def count(self, event_type: str) -> int:
        """Return the number of captured events matching the given type.

        Args:
            event_type: The event type string to count.

        Returns:
            Number of matching events.
        """
        return len(self.of_type(event_type))
