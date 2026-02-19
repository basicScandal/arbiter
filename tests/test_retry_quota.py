"""Tests for daily quota detection in Gemini retry logic."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.genai.errors import ClientError, ServerError

from src.resilience.retry import DailyQuotaExhausted, _is_daily_quota, _retry_if_rate_limited


def _make_429_error(message: str) -> ClientError:
    """Create a ClientError that looks like a Gemini 429."""
    error = ClientError(429, message)
    error.code = 429
    return error


class TestIsDailyQuota:
    """Tests for _is_daily_quota helper."""

    def test_detects_per_day_quota_id(self):
        error = _make_429_error(
            "quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier"
        )
        assert _is_daily_quota(error) is True

    def test_detects_per_day_in_details(self):
        error = _make_429_error(
            '{"quotaMetric": "requests", "quotaId": "SomePerDayLimit"}'
        )
        assert _is_daily_quota(error) is True

    def test_per_minute_is_not_daily(self):
        error = _make_429_error(
            "quotaId: GenerateRequestsPerMinutePerProjectPerModel"
        )
        assert _is_daily_quota(error) is False

    def test_generic_429_is_not_daily(self):
        error = _make_429_error("Rate limit exceeded, retry in 5s")
        assert _is_daily_quota(error) is False


class TestRetryIfRateLimited:
    """Tests for _retry_if_rate_limited retry predicate."""

    def _make_retry_state(self, error: Exception) -> MagicMock:
        """Build a mock retry_state with a failed outcome."""
        state = MagicMock()
        outcome = MagicMock()
        outcome.failed = True
        outcome.exception.return_value = error
        state.outcome = outcome
        return state

    def test_retries_per_minute_429(self):
        predicate = _retry_if_rate_limited()
        error = _make_429_error(
            "Rate limit exceeded, retry in 5s"
        )
        state = self._make_retry_state(error)
        assert predicate(state) is True

    def test_raises_on_daily_quota(self):
        predicate = _retry_if_rate_limited()
        error = _make_429_error(
            "quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier"
        )
        state = self._make_retry_state(error)
        with pytest.raises(DailyQuotaExhausted):
            predicate(state)

    def test_retries_server_error(self):
        predicate = _retry_if_rate_limited()
        error = ServerError(500, "Internal server error")
        state = self._make_retry_state(error)
        assert predicate(state) is True

    def test_does_not_retry_auth_error(self):
        predicate = _retry_if_rate_limited()
        error = ClientError(401, "Invalid API key")
        error.code = 401
        state = self._make_retry_state(error)
        assert predicate(state) is False

    def test_does_not_retry_success(self):
        predicate = _retry_if_rate_limited()
        state = MagicMock()
        outcome = MagicMock()
        outcome.failed = False
        state.outcome = outcome
        assert predicate(state) is False

    def test_does_not_retry_none_outcome(self):
        predicate = _retry_if_rate_limited()
        state = MagicMock()
        state.outcome = None
        assert predicate(state) is False


class TestDailyQuotaExhausted:
    """Tests for the DailyQuotaExhausted exception."""

    def test_is_exception(self):
        exc = DailyQuotaExhausted("quota hit")
        assert isinstance(exc, Exception)

    def test_preserves_message(self):
        exc = DailyQuotaExhausted("daily limit reached")
        assert "daily limit reached" in str(exc)
