"""Tests for the Gemini circuit breaker with half-open recovery."""

from __future__ import annotations

import time
from unittest.mock import patch

from src.resilience.circuit_breaker import GeminiCircuitBreaker


class TestGeminiCircuitBreaker:
    """Tests for GeminiCircuitBreaker state machine."""

    def test_starts_closed_and_available(self):
        cb = GeminiCircuitBreaker()
        assert cb.state == "closed"
        assert cb.available is True

    def test_trip_makes_unavailable(self):
        cb = GeminiCircuitBreaker()
        cb.trip()
        assert cb.state == "open"
        assert cb.available is False

    def test_trip_is_idempotent(self):
        cb = GeminiCircuitBreaker()
        cb.trip()
        cb.trip()
        assert cb.available is False

    def test_shared_across_components(self):
        """A single breaker instance should be shared across engines."""
        cb = GeminiCircuitBreaker()
        assert cb.available is True
        cb.trip()
        assert cb.available is False


class TestHalfOpenRecovery:
    """Tests for the half-open probe and recovery flow."""

    def test_transitions_to_half_open_after_cooldown(self):
        cb = GeminiCircuitBreaker(initial_cooldown=0.1)
        cb.trip()
        assert cb.state == "open"
        assert cb.available is False

        time.sleep(0.15)

        assert cb.state == "half_open"
        assert cb.available is True

    def test_probe_success_resets_to_closed(self):
        cb = GeminiCircuitBreaker(initial_cooldown=0.1)
        cb.trip()
        time.sleep(0.15)

        assert cb.state == "half_open"
        cb.record_success()

        assert cb.state == "closed"
        assert cb.available is True

    def test_probe_failure_reopens_with_extended_cooldown(self):
        cb = GeminiCircuitBreaker(initial_cooldown=0.1, extended_cooldown=0.2)
        cb.trip()
        time.sleep(0.15)

        assert cb.state == "half_open"
        cb.trip()  # Probe failed

        assert cb.state == "open"
        assert cb.available is False

        # Should NOT be half-open yet (extended cooldown is 0.2s)
        time.sleep(0.1)
        assert cb.state == "open"

        # After extended cooldown elapses
        time.sleep(0.15)
        assert cb.state == "half_open"
        assert cb.available is True

    def test_record_success_noop_when_closed(self):
        cb = GeminiCircuitBreaker()
        cb.record_success()  # Should not error
        assert cb.state == "closed"


class TestPermanentTrip:
    """Tests for permanent trip (daily quota exhaustion)."""

    def test_trip_permanent_stays_open_forever(self):
        cb = GeminiCircuitBreaker(initial_cooldown=0.05)
        cb.trip_permanent()

        assert cb.state == "open"
        assert cb.available is False

        # Even after cooldown, stays open
        time.sleep(0.1)
        assert cb.state == "open"
        assert cb.available is False

    def test_trip_permanent_is_idempotent(self):
        cb = GeminiCircuitBreaker()
        cb.trip_permanent()
        cb.trip_permanent()
        assert cb.available is False

    def test_transient_trip_ignored_after_permanent(self):
        cb = GeminiCircuitBreaker()
        cb.trip_permanent()
        cb.trip()  # Should be ignored
        assert cb.available is False

    def test_record_success_ignored_after_permanent(self):
        cb = GeminiCircuitBreaker(initial_cooldown=0.05)
        cb.trip_permanent()
        time.sleep(0.1)
        cb.record_success()  # Should not reset
        assert cb.available is False


class TestManualReset:
    """Tests for manual reset."""

    def test_reset_clears_transient_trip(self):
        cb = GeminiCircuitBreaker()
        cb.trip()
        cb.reset()
        assert cb.state == "closed"
        assert cb.available is True

    def test_reset_clears_permanent_trip(self):
        cb = GeminiCircuitBreaker()
        cb.trip_permanent()
        cb.reset()
        assert cb.state == "closed"
        assert cb.available is True

    def test_reset_restores_initial_cooldown(self):
        cb = GeminiCircuitBreaker(initial_cooldown=0.1, extended_cooldown=0.3)
        cb.trip()
        time.sleep(0.15)
        cb.trip()  # Extended cooldown
        cb.reset()

        # Trip again -- should use initial cooldown, not extended
        cb.trip()
        time.sleep(0.15)
        assert cb.state == "half_open"
