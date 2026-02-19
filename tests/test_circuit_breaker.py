"""Tests for the Gemini circuit breaker."""

from __future__ import annotations

from src.resilience.circuit_breaker import GeminiCircuitBreaker


class TestGeminiCircuitBreaker:
    """Tests for GeminiCircuitBreaker."""

    def test_starts_available(self):
        cb = GeminiCircuitBreaker()
        assert cb.available is True

    def test_trip_makes_unavailable(self):
        cb = GeminiCircuitBreaker()
        cb.trip()
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
        # Any component holding a reference sees the tripped state
        assert cb.available is False
