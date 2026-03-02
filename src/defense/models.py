"""Pydantic data models for the defense pipeline.

Defines types for injection patterns, detection results, injection attempts,
sanitized output bundles, and defense-layer capture events.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.capture.models import CaptureEvent

# ---------------------------------------------------------------------------
# Core defense types
# ---------------------------------------------------------------------------


class InjectionPattern(BaseModel):
    """A single regex-based injection detection pattern."""

    name: str
    pattern: str
    severity: str  # "high", "medium", or "low"
    category: str  # "instruction_override", "scoring", "role_manipulation", "extraction", "context_escape"


class DetectionResult(BaseModel):
    """Result from scanning text against injection patterns."""

    is_injection: bool
    matched_patterns: list[str] = []
    matched_text: str = ""
    confidence: str = "low"  # "high", "medium", "low"
    source: str = ""  # "visual", "verbal", or "observation"


class InjectionAttempt(BaseModel):
    """A confirmed injection attempt for logging and roasting."""

    timestamp: float
    injection_type: str  # "visual", "verbal", or "observation"
    content: str
    pattern: str  # comma-joined names of matched patterns
    confidence: str
    team_name: str = ""


class SanitizedOutput(BaseModel):
    """Clean output bundle for downstream consumers (Phase 3/4).

    Contains only verified-clean observations and transcripts, plus
    all detected injection attempts for reference and roast delivery.
    """

    team_name: str
    observations: list[str]  # clean Gemini observations (tainted ones removed)
    transcripts: list[str]  # clean transcript text segments
    injection_attempts: list[InjectionAttempt]
    demo_duration: float
    roasts: list[str] = []  # generated roast responses


# ---------------------------------------------------------------------------
# Defense events extending CaptureEvent
# ---------------------------------------------------------------------------


class InjectionDetected(CaptureEvent):
    """Emitted when an injection attempt is detected."""

    event_type: str = "injection_detected"
    attempt: InjectionAttempt


class RoastGenerated(CaptureEvent):
    """Emitted when a roast is generated for an injection attempt."""

    event_type: str = "roast_generated"
    roast: str
    attempt: InjectionAttempt


class ObservationVerified(CaptureEvent):
    """Emitted when observations are sanitized and verified for downstream use."""

    event_type: str = "observation_verified"
    output: SanitizedOutput
