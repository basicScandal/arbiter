"""Tests for GeminiSession exponential backoff behaviour.

Validates the _Backoff helper used by GeminiSession for both receive-loop
errors (transient) and connection-level errors (full reconnect).
"""

from __future__ import annotations

from src.capture.gemini_session import _Backoff


class TestBackoff:
    """Tests for the _Backoff exponential backoff tracker."""

    def test_initial_delay(self):
        """First delay is the initial value."""
        b = _Backoff(initial=1.0, maximum=30.0)
        assert b.next_delay() == 1.0

    def test_exponential_growth(self):
        """Delay doubles on each call (default multiplier=2)."""
        b = _Backoff(initial=1.0, maximum=30.0)
        assert b.next_delay() == 1.0
        assert b.next_delay() == 2.0
        assert b.next_delay() == 4.0
        assert b.next_delay() == 8.0
        assert b.next_delay() == 16.0

    def test_caps_at_maximum(self):
        """Delay never exceeds the configured maximum."""
        b = _Backoff(initial=1.0, maximum=10.0)
        for _ in range(20):
            delay = b.next_delay()
        assert delay == 10.0

    def test_reset_returns_to_initial(self):
        """Reset brings delay back to initial value."""
        b = _Backoff(initial=2.0, maximum=30.0)
        b.next_delay()  # 2
        b.next_delay()  # 4
        b.next_delay()  # 8
        b.reset()
        assert b.next_delay() == 2.0

    def test_custom_multiplier(self):
        """Non-default multiplier is respected."""
        b = _Backoff(initial=1.0, maximum=100.0, multiplier=3.0)
        assert b.next_delay() == 1.0
        assert b.next_delay() == 3.0
        assert b.next_delay() == 9.0
        assert b.next_delay() == 27.0

    def test_connect_backoff_defaults(self):
        """Verify the defaults used by GeminiSession for connection backoff."""
        b = _Backoff(initial=2.0, maximum=30.0)
        delays = [b.next_delay() for _ in range(6)]
        assert delays == [2.0, 4.0, 8.0, 16.0, 30.0, 30.0]

    def test_receive_backoff_defaults(self):
        """Verify the defaults used by GeminiSession for receive-loop backoff."""
        b = _Backoff(initial=1.0, maximum=30.0)
        delays = [b.next_delay() for _ in range(7)]
        assert delays == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0]
