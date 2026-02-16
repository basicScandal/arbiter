"""Observation sanitizer that removes tainted content before the P-LLM boundary.

This is the critical security boundary of the defense pipeline. Observations
from Gemini may faithfully transcribe injection text from slides or speech
(Pitfall 4: quoted injection passthrough). The sanitizer scans each observation
and transcript segment, excluding entire entries that match injection patterns
at medium or high confidence. Per research anti-pattern guidance, we flag and
exclude whole observations rather than attempting word-level redaction.
"""

from __future__ import annotations

import logging

from src.defense.injection_detector import InjectionDetector
from src.defense.models import InjectionAttempt, SanitizedOutput

logger = logging.getLogger(__name__)


class ObservationSanitizer:
    """Strips tainted observations before they reach the privileged LLM."""

    def __init__(self, detector: InjectionDetector) -> None:
        self._detector = detector

    def sanitize_observations(
        self,
        observations: list[str],
        known_attempts: list[InjectionAttempt],
    ) -> list[str]:
        """Remove tainted observations at medium or high confidence.

        Each observation is scanned individually. If injection patterns are
        detected with medium or high confidence, the entire observation is
        excluded -- no partial redaction.

        Args:
            observations: Raw Gemini observations to sanitize.
            known_attempts: Previously detected injection attempts (for context).

        Returns:
            List of clean observations with tainted entries removed.
        """
        clean: list[str] = []
        removed = 0

        for observation in observations:
            result = self._detector.scan_observation(observation)
            if result.is_injection and result.confidence in ("medium", "high"):
                removed += 1
                logger.warning(
                    "Removed tainted observation: confidence=%s, patterns=%s, text=%r",
                    result.confidence,
                    result.matched_patterns,
                    observation[:100],
                )
            else:
                clean.append(observation)

        logger.info("Sanitized observations: %d/%d removed", removed, len(observations))
        return clean

    def sanitize_transcripts(
        self,
        transcripts: list[str],
        known_attempts: list[InjectionAttempt],
    ) -> list[str]:
        """Remove tainted transcript segments at medium or high confidence.

        Same approach as observation sanitization -- filter out segments
        that match injection patterns rather than attempting redaction.

        Args:
            transcripts: Raw transcript text segments to sanitize.
            known_attempts: Previously detected injection attempts (for context).

        Returns:
            List of clean transcript segments with tainted entries removed.
        """
        clean: list[str] = []
        removed = 0

        for transcript in transcripts:
            result = self._detector.scan(transcript, source="verbal")
            if result.is_injection and result.confidence in ("medium", "high"):
                removed += 1
                logger.warning(
                    "Removed tainted transcript: confidence=%s, patterns=%s, text=%r",
                    result.confidence,
                    result.matched_patterns,
                    transcript[:100],
                )
            else:
                clean.append(transcript)

        logger.info("Sanitized transcripts: %d/%d removed", removed, len(transcripts))
        return clean

    def create_sanitized_output(
        self,
        team_name: str,
        observations: list[str],
        transcripts: list[str],
        attempts: list[InjectionAttempt],
        duration: float,
        roasts: list[str] | None = None,
    ) -> SanitizedOutput:
        """Create a SanitizedOutput bundle with clean data for downstream consumers.

        Runs both observation and transcript sanitization, then packages the
        results with injection attempt records and roasts.

        Args:
            team_name: Name of the presenting team.
            observations: Raw Gemini observations.
            transcripts: Raw transcript text segments.
            attempts: All detected injection attempts.
            duration: Demo duration in seconds.
            roasts: Optional list of generated roast strings.

        Returns:
            SanitizedOutput with clean observations/transcripts and full
            injection attempt list for reference.
        """
        clean_observations = self.sanitize_observations(observations, attempts)
        clean_transcripts = self.sanitize_transcripts(transcripts, attempts)

        return SanitizedOutput(
            team_name=team_name,
            observations=clean_observations,
            transcripts=clean_transcripts,
            injection_attempts=attempts,
            demo_duration=duration,
            roasts=roasts or [],
        )
