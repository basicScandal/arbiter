"""Shared tenacity retry decorator configs for Gemini API calls.

Two configs are provided:
- GEMINI_RETRY: 3 attempts for interactive paths (commentary generation)
- GEMINI_RETRY_BACKGROUND: 5 attempts for background paths (scoring, deliberation)

Both use exponential backoff with jitter and retry on:
- Network-level exceptions (ConnectionError, TimeoutError, OSError)
- Gemini 429 rate-limit errors (ClientError with code 429)
- Gemini 5xx server errors (ServerError)

Auth errors and ValueError are NOT retried.
"""

from __future__ import annotations

import logging
import re

from google.genai.errors import ClientError, ServerError
from tenacity import (
    before_sleep_log,
    retry,
    retry_base,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)

_RETRYABLE_NETWORK = (ConnectionError, TimeoutError, OSError)


class _retry_if_rate_limited(retry_base):
    """Retry on Gemini 429 rate-limit or 5xx server errors."""

    def __call__(self, retry_state: object) -> bool:
        exc = getattr(retry_state, "outcome", None)
        if exc is None or not exc.failed:
            return False
        error = exc.exception()
        if isinstance(error, ClientError) and getattr(error, "code", 0) == 429:
            # Parse server-suggested delay if present (e.g. "retry in 9.8s")
            msg = str(error)
            match = re.search(r"retry in ([\d.]+)s", msg, re.IGNORECASE)
            if match:
                suggested = float(match.group(1))
                logger.info(
                    "Gemini rate-limited; server suggests %.1fs delay", suggested
                )
            return True
        if isinstance(error, ServerError):
            return True
        return False


_retry_condition = retry_if_exception_type(_RETRYABLE_NETWORK) | _retry_if_rate_limited()

GEMINI_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=15, jitter=2),
    retry=_retry_condition,
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
"""Retry decorator for interactive Gemini calls (3 attempts).

Used on commentary generation where latency matters. Retries on
network errors, 429 rate limits, and 5xx server errors.
"""

GEMINI_RETRY_BACKGROUND = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=2, max=30, jitter=3),
    retry=_retry_condition,
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
"""Retry decorator for background Gemini calls (5 attempts).

Used on scoring and deliberation where reliability matters more than
latency. Retries on network errors, 429 rate limits, and 5xx server errors.
"""
