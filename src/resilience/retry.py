"""Shared tenacity retry decorator configs for Gemini API calls.

Two configs are provided:
- GEMINI_RETRY: 3 attempts for interactive paths (commentary generation)
- GEMINI_RETRY_BACKGROUND: 5 attempts for background paths (scoring, deliberation)

Both use exponential backoff with jitter and retry only on network-level
exceptions (ConnectionError, TimeoutError, OSError). Auth errors and
ValueError are NOT retried.
"""

from __future__ import annotations

import logging

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)

_RETRYABLE_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)

GEMINI_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10, jitter=2),
    retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
"""Retry decorator for interactive Gemini calls (3 attempts).

Used on commentary generation where latency matters. Retries on
ConnectionError, TimeoutError, and OSError only.
"""

GEMINI_RETRY_BACKGROUND = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=10, jitter=2),
    retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
"""Retry decorator for background Gemini calls (5 attempts).

Used on scoring and deliberation where reliability matters more than
latency. Retries on ConnectionError, TimeoutError, and OSError only.
"""
