"""Pipeline-level Gemini circuit breaker with half-open recovery.

Tracks whether Gemini's daily quota has been exhausted or a transient
failure has occurred. Supports three states:

  - CLOSED: Gemini is available, all calls go through normally.
  - OPEN: Gemini is unavailable. After a cooldown period, transitions
    to half-open to probe for recovery.
  - HALF_OPEN: One probe request is allowed. If it succeeds, the breaker
    resets to closed. If it fails, the breaker reopens with a longer cooldown.

For permanent failures (daily quota exhaustion), use trip_permanent() which
disables recovery entirely.

Thread-safe via simple state + monotonic time -- sufficient because the
pipeline runs in a single asyncio event loop.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

# Default cooldown periods (seconds)
_INITIAL_COOLDOWN = 60.0
_EXTENDED_COOLDOWN = 120.0


class GeminiCircuitBreaker:
    """Shared circuit breaker for Gemini API availability.

    Supports transient failure recovery via half-open state. Components
    check `available` before calling Gemini. After a transient trip, the
    breaker automatically transitions to half-open after the cooldown
    period, allowing a single probe request.

    For daily quota exhaustion (permanent), use trip_permanent() to
    disable recovery for the rest of the session.
    """

    def __init__(
        self,
        initial_cooldown: float = _INITIAL_COOLDOWN,
        extended_cooldown: float = _EXTENDED_COOLDOWN,
    ) -> None:
        self._state: str = "closed"  # "closed", "open", "half_open"
        self._tripped_at: float = 0.0
        self._cooldown: float = initial_cooldown
        self._initial_cooldown = initial_cooldown
        self._extended_cooldown = extended_cooldown
        self._permanent = False
        self._probe_in_flight = False

    @property
    def state(self) -> str:
        """Current breaker state: 'closed', 'open', or 'half_open'."""
        self._maybe_transition_to_half_open()
        return self._state

    @property
    def available(self) -> bool:
        """Whether Gemini should be attempted.

        Returns True when closed or when half-open AND no probe is already
        in flight. This prevents thundering herd: only the first caller
        after cooldown gets to probe, others wait for the next cycle.
        """
        self._maybe_transition_to_half_open()
        if self._state == "closed":
            return True
        if self._state == "half_open":
            if not self._probe_in_flight:
                self._probe_in_flight = True
                return True
            return False
        return False

    def trip(self) -> None:
        """Trip the breaker due to a transient failure.

        Enters open state with cooldown. After the cooldown elapses,
        the breaker transitions to half-open for a probe request.
        """
        if self._permanent:
            return  # Already permanently tripped

        if self._state == "closed":
            logger.warning(
                "Gemini circuit breaker tripped (transient) -- "
                "will probe for recovery in %.0fs", self._cooldown,
            )
        elif self._state == "half_open":
            # Probe failed -- extend cooldown
            self._cooldown = self._extended_cooldown
            logger.warning(
                "Gemini circuit breaker probe failed -- "
                "extending cooldown to %.0fs", self._cooldown,
            )

        self._state = "open"
        self._tripped_at = time.monotonic()
        self._probe_in_flight = False

    def trip_permanent(self) -> None:
        """Trip the breaker permanently (e.g., daily quota exhaustion).

        No recovery is possible -- Gemini stays unavailable for the
        remainder of this pipeline run.
        """
        if not self._permanent:
            logger.warning(
                "Gemini circuit breaker tripped PERMANENTLY -- "
                "all subsequent calls will use fallback providers"
            )
            self._state = "open"
            self._permanent = True
            self._probe_in_flight = False

    def record_success(self) -> None:
        """Record a successful Gemini call.

        If in half-open state (probe succeeded), resets the breaker
        to closed with the initial cooldown restored.
        """
        if self._state == "half_open":
            logger.info(
                "Gemini circuit breaker probe succeeded -- "
                "resetting to closed"
            )
            self._state = "closed"
            self._cooldown = self._initial_cooldown
            self._probe_in_flight = False

    def reset(self) -> None:
        """Manually reset the breaker to closed state.

        Clears permanent flag and restores initial cooldown.
        """
        self._state = "closed"
        self._permanent = False
        self._cooldown = self._initial_cooldown
        self._tripped_at = 0.0
        self._probe_in_flight = False
        logger.info("Gemini circuit breaker manually reset to closed")

    def _maybe_transition_to_half_open(self) -> None:
        """Transition from open to half-open if cooldown has elapsed."""
        if self._state != "open" or self._permanent:
            return

        elapsed = time.monotonic() - self._tripped_at
        if elapsed >= self._cooldown:
            self._state = "half_open"
            logger.info(
                "Gemini circuit breaker entering half-open state -- "
                "next call is a probe (cooldown=%.0fs elapsed)", elapsed,
            )
