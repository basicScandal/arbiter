"""Structured logging of all injection attempts.

Records every attempt with timestamp, type, content, matched patterns,
and team attribution for downstream scoring notes and audit trail.
"""

from __future__ import annotations

import logging

from src.defense.models import InjectionAttempt

logger = logging.getLogger("arbiter.defense.injections")


class InjectionLogger:
    """Records and retrieves injection attempts with structured logging."""

    def __init__(self) -> None:
        self._attempts: list[InjectionAttempt] = []

    def log(self, attempt: InjectionAttempt) -> None:
        """Record an injection attempt and emit a structured WARNING log.

        Args:
            attempt: The injection attempt to record.
        """
        self._attempts.append(attempt)
        logger.warning(
            "INJECTION DETECTED | type=%s | confidence=%s | team=%s | patterns=%s | content=%s",
            attempt.injection_type,
            attempt.confidence,
            attempt.team_name,
            attempt.pattern,
            attempt.content[:100],
        )

    def get_attempts(self) -> list[InjectionAttempt]:
        """Return a copy of all recorded injection attempts."""
        return list(self._attempts)

    def clear(self) -> None:
        """Clear all recorded attempts. Call between events if needed."""
        self._attempts.clear()
