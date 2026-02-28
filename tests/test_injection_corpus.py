"""Corpus-driven test suite for InjectionDetector pattern coverage.

Validates that:
- All attack payloads are detected with expected patterns and confidence.
- Legitimate hackathon discourse does not trigger high-confidence alerts.
- Aggregate detection and false-positive rates meet production thresholds.
- Every pattern in INJECTION_PATTERNS is exercised by at least one payload.
"""

from __future__ import annotations

import pytest

from src.defense.injection_detector import INJECTION_PATTERNS, InjectionDetector
from tests.injection_corpus import ATTACK_PAYLOADS, FALSE_POSITIVE_TEXTS

# ---------------------------------------------------------------------------
# Confidence ordering (for "at least this level" assertions)
# ---------------------------------------------------------------------------

_CONFIDENCE_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


def _confidence_gte(actual: str, expected: str) -> bool:
    """Return True if *actual* confidence is >= *expected* confidence."""
    return _CONFIDENCE_RANK.get(actual, -1) >= _CONFIDENCE_RANK.get(expected, -1)


# ---------------------------------------------------------------------------
# Shared detector instance (stateless, safe to reuse)
# ---------------------------------------------------------------------------

_detector = InjectionDetector()


# ---------------------------------------------------------------------------
# TestAttackDetection
# ---------------------------------------------------------------------------


class TestAttackDetection:
    """Each attack payload must be detected with expected patterns and confidence."""

    @staticmethod
    def _id(payload: dict) -> str:
        """Generate a human-readable test ID from a payload."""
        return payload["description"][:72]

    @pytest.mark.parametrize(
        "payload",
        ATTACK_PAYLOADS,
        ids=[p["description"][:72] for p in ATTACK_PAYLOADS],
    )
    def test_attack_is_detected(self, payload: dict) -> None:
        result = _detector.scan(payload["text"], source=payload["vector"])

        # Must be flagged as injection
        assert result.is_injection, (
            f"Expected injection detection for: {payload['description']}\n"
            f"  text: {payload['text']!r}\n"
            f"  matched_patterns: {result.matched_patterns}"
        )

        # At least one expected pattern must appear in matched_patterns
        matched_expected = set(payload["expected_patterns"]) & set(
            result.matched_patterns
        )
        assert matched_expected, (
            f"None of the expected patterns matched.\n"
            f"  expected: {payload['expected_patterns']}\n"
            f"  actual:   {result.matched_patterns}\n"
            f"  text:     {payload['text']!r}"
        )

        # Confidence must be at the expected level or higher
        assert _confidence_gte(result.confidence, payload["expected_confidence"]), (
            f"Confidence too low.\n"
            f"  expected >= {payload['expected_confidence']}\n"
            f"  actual:     {result.confidence}\n"
            f"  patterns:   {result.matched_patterns}\n"
            f"  text:       {payload['text']!r}"
        )


# ---------------------------------------------------------------------------
# TestFalsePositiveDefense
# ---------------------------------------------------------------------------


class TestFalsePositiveDefense:
    """Legitimate hackathon text must not trigger high-confidence alerts."""

    @pytest.mark.parametrize(
        "entry",
        FALSE_POSITIVE_TEXTS,
        ids=[e["description"][:72] for e in FALSE_POSITIVE_TEXTS],
    )
    def test_benign_text_not_high_confidence(self, entry: dict) -> None:
        result = _detector.scan(entry["text"], source="observation")

        # Either not flagged at all, or flagged at low confidence only.
        # We tolerate "low" because hackathon presenters quoting attack
        # phrases will inevitably trigger surface-level pattern matches.
        if result.is_injection:
            assert result.confidence != "high", (
                f"Legitimate text flagged at HIGH confidence.\n"
                f"  description: {entry['description']}\n"
                f"  context:     {entry['context']}\n"
                f"  patterns:    {result.matched_patterns}\n"
                f"  text:        {entry['text']!r}"
            )


# ---------------------------------------------------------------------------
# TestDetectionMetrics
# ---------------------------------------------------------------------------


class TestDetectionMetrics:
    """Aggregate detection and false-positive rates must meet thresholds."""

    def test_detection_rate(self) -> None:
        """At least 95% of attack payloads must be detected."""
        detected = 0
        for payload in ATTACK_PAYLOADS:
            result = _detector.scan(payload["text"], source=payload["vector"])
            if result.is_injection:
                detected += 1

        rate = detected / len(ATTACK_PAYLOADS)
        assert rate >= 0.95, (
            f"Detection rate {rate:.2%} below 95% threshold "
            f"({detected}/{len(ATTACK_PAYLOADS)} detected)"
        )

    def test_false_positive_rate(self) -> None:
        """Fewer than 5% of benign texts should flag at medium+ confidence."""
        false_positives = 0
        for entry in FALSE_POSITIVE_TEXTS:
            result = _detector.scan(entry["text"], source="observation")
            if result.is_injection and result.confidence in ("medium", "high"):
                false_positives += 1

        rate = false_positives / len(FALSE_POSITIVE_TEXTS)
        assert rate < 0.05, (
            f"False positive rate {rate:.2%} exceeds 5% threshold "
            f"({false_positives}/{len(FALSE_POSITIVE_TEXTS)} false positives at medium+ confidence)"
        )


# ---------------------------------------------------------------------------
# TestAllPatternsExercised
# ---------------------------------------------------------------------------


class TestAllPatternsExercised:
    """Every pattern in INJECTION_PATTERNS must be triggered by at least one payload."""

    def test_all_patterns_covered(self) -> None:
        # Collect all pattern names from the detector's pattern library
        all_pattern_names = {p.name for p in INJECTION_PATTERNS}

        # Collect all pattern names that are actually triggered by the corpus
        triggered: set[str] = set()
        for payload in ATTACK_PAYLOADS:
            result = _detector.scan(payload["text"], source=payload["vector"])
            triggered.update(result.matched_patterns)

        missing = all_pattern_names - triggered
        assert not missing, (
            f"The following patterns were never triggered by any attack payload:\n"
            f"  {sorted(missing)}\n"
            f"Add attack payloads that exercise these patterns."
        )

    def test_all_patterns_declared_in_corpus(self) -> None:
        """Every pattern name referenced in ATTACK_PAYLOADS exists in INJECTION_PATTERNS."""
        all_pattern_names = {p.name for p in INJECTION_PATTERNS}

        referenced: set[str] = set()
        for payload in ATTACK_PAYLOADS:
            referenced.update(payload["expected_patterns"])

        unknown = referenced - all_pattern_names
        assert not unknown, (
            f"Corpus references patterns not in INJECTION_PATTERNS:\n"
            f"  {sorted(unknown)}\n"
            f"Fix the expected_patterns in the corpus or add the pattern to the detector."
        )
