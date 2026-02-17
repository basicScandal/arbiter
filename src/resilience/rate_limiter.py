"""Gemini API rate limiter to prevent 429 errors from concurrent calls.

Provides a GeminiRateLimiter singleton with a semaphore that limits
concurrent Gemini API calls across all components (commentary, Q&A, provider).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

logger = logging.getLogger(__name__)


class GeminiRateLimiter:
    """Singleton rate limiter for Gemini API calls.

    Limits concurrent Gemini API calls to prevent 429 rate limit errors.
    Uses a semaphore with max 2 concurrent calls across all components.
    """

    _instance: GeminiRateLimiter | None = None

    def __init__(self, max_concurrent: int = 2) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)

    @classmethod
    def default(cls) -> GeminiRateLimiter:
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @asynccontextmanager
    async def acquire(self, caller: str = "") -> AsyncIterator[None]:
        """Acquire rate limiter semaphore for a Gemini API call.

        Args:
            caller: Component name for debug logging (e.g., "commentary").

        Yields:
            None when semaphore is acquired.
        """
        logger.debug("Rate limiter: %s acquiring semaphore", caller or "unknown")
        async with self._semaphore:
            logger.debug("Rate limiter: %s acquired semaphore", caller or "unknown")
            try:
                yield
            finally:
                logger.debug("Rate limiter: %s released semaphore", caller or "unknown")
