"""Pipeline-level Gemini circuit breaker.

Tracks whether Gemini's daily quota has been exhausted. Once tripped,
all pipeline components skip Gemini and go straight to fallback providers,
eliminating wasted API round-trips.

Thread-safe via simple boolean flag -- sufficient because the replay
pipeline runs in a single asyncio event loop.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class GeminiCircuitBreaker:
    """Shared circuit breaker for Gemini API availability.

    Once tripped (daily quota exhausted), all components that check
    this breaker skip Gemini entirely and use fallback providers.
    The breaker does NOT reset during a pipeline run -- daily quota
    exhaustion is terminal until the quota resets (next day).
    """

    def __init__(self) -> None:
        self._available = True

    @property
    def available(self) -> bool:
        """Whether Gemini should be attempted."""
        return self._available

    def trip(self) -> None:
        """Mark Gemini as unavailable for the remainder of this pipeline run."""
        if self._available:
            logger.warning(
                "Gemini circuit breaker tripped -- all subsequent "
                "calls will use fallback providers"
            )
            self._available = False
