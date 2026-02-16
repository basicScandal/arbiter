"""Service health tracking with exponential recovery windows.

ServiceHealth records per-component healthy/unhealthy state. Unhealthy
services become eligible for retry after a recovery window that doubles
on each consecutive failure, capped at 600 seconds. Follows the
module-level singleton pattern established by EventBus (default_health).
"""

from __future__ import annotations

import time


class ServiceHealth:
    """Tracks per-component health with timed exponential recovery windows.

    Components start as healthy (never tracked = healthy). When marked
    unhealthy, they remain so until the recovery window elapses, at which
    point is_healthy() returns True to allow a retry attempt. Consecutive
    failures double the recovery window up to a 600-second cap.

    Args:
        recovery_window: Base recovery duration in seconds. Defaults to 60.
    """

    def __init__(self, recovery_window: float = 60.0) -> None:
        self._recovery_window = recovery_window
        self._healthy: dict[str, bool] = {}
        self._last_failure: dict[str, float] = {}
        self._failure_count: dict[str, int] = {}

    def mark_healthy(self, service: str) -> None:
        """Mark a service as healthy, resetting its failure count."""
        self._healthy[service] = True
        self._failure_count[service] = 0

    def mark_unhealthy(self, service: str) -> None:
        """Mark a service as unhealthy, recording failure time and incrementing count."""
        self._healthy[service] = False
        self._last_failure[service] = time.monotonic()
        self._failure_count[service] = self._failure_count.get(service, 0) + 1

    def is_healthy(self, service: str) -> bool:
        """Check if a service is healthy or eligible for retry.

        Returns True if the service has never been tracked, is currently
        healthy, or the exponential recovery window has elapsed since the
        last failure (allowing a retry attempt).

        The recovery window doubles with each consecutive failure:
        base * 2^(failure_count - 1), capped at 600 seconds.
        """
        if service not in self._healthy:
            return True
        if self._healthy[service]:
            return True

        # Unhealthy -- check if recovery window has elapsed
        failures = self._failure_count.get(service, 1)
        backoff = min(
            self._recovery_window * (2 ** (failures - 1)),
            600.0,
        )
        elapsed = time.monotonic() - self._last_failure.get(service, 0.0)
        return elapsed >= backoff

    def get_status(self) -> dict[str, bool]:
        """Return current health status for all tracked services."""
        return {
            service: self.is_healthy(service) for service in self._healthy
        }

    def failure_count(self, service: str) -> int:
        """Return the consecutive failure count for a service."""
        return self._failure_count.get(service, 0)


default_health = ServiceHealth()
"""Module-level singleton following the EventBus pattern."""
