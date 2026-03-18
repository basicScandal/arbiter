"""Regex-based injection pattern detection with confidence scoring.

Provides fast (<1ms) heuristic pattern matching against known prompt
injection attack vocabulary. Multiple pattern matches raise confidence
to reduce false positives at a security hackathon where presenters
legitimately discuss injection and security topics.
"""

from __future__ import annotations

import base64
import logging
import re
import unicodedata

from src.defense.models import DetectionResult, InjectionPattern

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Injection pattern library
# ---------------------------------------------------------------------------

INJECTION_PATTERNS: list[InjectionPattern] = [
    # --- instruction_override (high severity) ---
    InjectionPattern(
        name="ignore_previous",
        pattern=r"(?i)\b(ignore|disregard|forget)\b.{0,30}\b(previous|above|prior|all)\b.{0,30}\b(instructions?|prompts?|rules?)\b",
        severity="high",
        category="instruction_override",
    ),
    InjectionPattern(
        name="new_instructions",
        pattern=r"(?i)\b(new|updated|real|actual|true)\b.{0,20}\b(instructions?|directives?|orders?|rules?)\b",
        severity="high",
        category="instruction_override",
    ),
    # --- scoring (high severity) ---
    InjectionPattern(
        name="score_manipulation",
        pattern=r"(?i)\b(give|assign|score|rate|award)\b.{0,30}\b(10|perfect|full|maximum|highest)\b",
        severity="high",
        category="scoring",
    ),
    InjectionPattern(
        name="score_override",
        pattern=r"(?i)\b(score|rating|points?)\b.{0,20}\b(must be|should be|is now|set to)\b.{0,10}\b\d",
        severity="high",
        category="scoring",
    ),
    InjectionPattern(
        name="prize_manipulation",
        pattern=r"(?i)\b(give|award|grant)\b.{0,30}\b(prize|winner|first place|grand prize|winning)\b",
        severity="high",
        category="scoring",
    ),
    # --- role_manipulation (medium severity) ---
    InjectionPattern(
        name="role_override",
        pattern=r"(?i)\b(you are|act as|pretend|behave as|your role is)\b.{0,30}\b(not a judge|helpful assistant|friendly|compliant)\b",
        severity="medium",
        category="role_manipulation",
    ),
    InjectionPattern(
        name="identity_reset",
        pattern=r"(?i)\b(you are now|from now on|henceforth|starting now)\b",
        severity="medium",
        category="role_manipulation",
    ),
    InjectionPattern(
        name="prompt_override",
        pattern=r"(?i)\b(override|overwrite|replace|bypass|reset)\b.{0,20}\b(system|initial|original|scoring)?\s*(prompt|instructions?|rules?|config)\b",
        severity="high",
        category="instruction_override",
    ),
    # --- extraction (medium severity) ---
    InjectionPattern(
        name="prompt_extraction",
        pattern=r"(?i)\b(system prompt|initial prompt|reveal|show|display|repeat)\b.{0,30}\b(instructions?|prompt|rules?|configuration)\b",
        severity="medium",
        category="extraction",
    ),
    InjectionPattern(
        name="output_rules",
        pattern=r"(?i)\b(print|output|display|echo|return)\b.{0,20}\b(above|system|hidden|secret|internal)\b",
        severity="medium",
        category="extraction",
    ),
    # --- context_escape (high severity) ---
    InjectionPattern(
        name="delimiter_escape",
        pattern=r"(?i)(```|</?system>|</?user>|</?assistant>|\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>)",
        severity="high",
        category="context_escape",
    ),
    InjectionPattern(
        name="xml_injection",
        pattern=r"(?i)(<\/?(?:tool|function|command|execute|admin|root)>)",
        severity="high",
        category="context_escape",
    ),
]


def _try_decode_base64(text: str) -> str:
    """Find and decode base64 strings > 20 chars, append decoded text for scanning."""
    decoded_parts = []
    for match in re.finditer(r'[A-Za-z0-9+/=]{20,}', text):
        candidate = match.group()
        try:
            decoded = base64.b64decode(candidate, validate=True).decode('utf-8', errors='ignore')
            if decoded.strip():
                decoded_parts.append(decoded)
        except Exception:
            pass
    if decoded_parts:
        return text + " " + " ".join(decoded_parts)
    return text


class InjectionDetector:
    """Scans text for injection patterns with confidence scoring.

    Confidence levels:
        - "high": 2+ high-severity matches
        - "medium": 1 high-severity or 2+ medium-severity matches
        - "low": 1 medium/low-severity match
    """

    def __init__(self, patterns: list[InjectionPattern] | None = None) -> None:
        self._patterns = patterns if patterns is not None else INJECTION_PATTERNS

    def scan(self, text: str, source: str) -> DetectionResult:
        """Scan text against all injection patterns.

        Args:
            text: The text to scan for injection patterns.
            source: Origin of the text -- "visual", "verbal", or "observation".

        Returns:
            DetectionResult with match details and confidence scoring.
        """
        if not text or not text.strip():
            return DetectionResult(is_injection=False, source=source)

        # Replace zero-width, invisible, and bidirectional override characters
        # with spaces so word boundaries survive (attackers insert these to
        # break regex patterns or hide injections via RTL/LTR text tricks)
        text = re.sub(
            r"[\u200b\u200c\u200d\u00ad\u034f\ufeff\u2060"
            r"\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
            r"\u2066\u2067\u2068\u2069]",
            " ",
            text,
        )
        # Normalize unicode to catch homoglyph evasion (e.g., fullwidth chars)
        normalized = unicodedata.normalize("NFKC", text)
        # Decode potential base64 strings and scan those too
        normalized = _try_decode_base64(normalized)
        text = normalized

        matched_patterns: list[str] = []
        first_matched_text: str = ""
        high_count = 0
        medium_count = 0

        for pattern in self._patterns:
            match = re.search(pattern.pattern, text)
            if match:
                matched_patterns.append(pattern.name)
                if not first_matched_text:
                    first_matched_text = match.group(0)

                if pattern.severity == "high":
                    high_count += 1
                elif pattern.severity == "medium":
                    medium_count += 1

        if not matched_patterns:
            return DetectionResult(is_injection=False, source=source)

        # Compute confidence based on severity distribution
        if high_count >= 2:
            confidence = "high"
        elif high_count == 1 or medium_count >= 2:
            confidence = "medium"
        else:
            confidence = "low"

        result = DetectionResult(
            is_injection=True,
            matched_patterns=matched_patterns,
            matched_text=first_matched_text,
            confidence=confidence,
            source=source,
        )

        logger.info(
            "Injection detected [%s]: confidence=%s, patterns=%s, text=%r",
            source,
            confidence,
            matched_patterns,
            first_matched_text[:80],
        )

        return result

    def scan_visual(self, text: str) -> DetectionResult:
        """Scan OCR-extracted text for visual injection patterns."""
        return self.scan(text, source="visual")

    def scan_verbal(self, text: str) -> DetectionResult:
        """Scan transcript text for verbal injection patterns."""
        return self.scan(text, source="verbal")

    def scan_observation(self, text: str) -> DetectionResult:
        """Scan Gemini observation text for injection residue."""
        return self.scan(text, source="observation")
