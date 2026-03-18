"""Regex-based injection pattern detection with confidence scoring.

Provides fast (<1ms) heuristic pattern matching against known prompt
injection attack vocabulary. Multiple pattern matches raise confidence
to reduce false positives at a security hackathon where presenters
legitimately discuss injection and security topics.

Also provides semantic heuristic detection (scan_semantic) that catches
manipulation using natural language: rubric phrase echoing, self-evaluative
language, fabricated evidence markers, and multi-language injection phrases.
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


# ---------------------------------------------------------------------------
# Semantic detection constants
# ---------------------------------------------------------------------------

# Exact phrases lifted from GENERAL_CRITERIA and EXTENDED_CRITERIA level
# descriptors in src/scoring/rubric.py.  Two or more of these appearing
# together in an observation text is a strong signal that someone copy-pasted
# the rubric into their demo output to bias the judge.
_RUBRIC_PHRASES: frozenset[str] = frozenset(
    {
        # Technical Execution levels
        "flawless implementation",
        "production-quality",
        "handles edge cases",
        "solid implementation with minor gaps",
        "functional but rough",
        "obvious shortcuts",
        "partially working",
        "significant bugs",
        "barely functional",
        # Innovation levels
        "groundbreaking novel approach",
        "clearly innovative with unique angle",
        "some novelty but mostly established techniques",
        "incremental or derivative",
        "no discernible innovation",
        # Demo Quality levels
        "flawless live demo",
        "masterful explanation",
        "compelling narrative",
        "solid demo with good explanation",
        "minor hiccups",
        "demo works but explanation unclear",
        "demo partially works",
        "confusing presentation",
        "demo fails or no meaningful demonstration",
        # Impact levels (EXTENDED_CRITERIA)
        "immediately deployable",
        "addresses critical real-world need",
        "strong real-world potential with clear use case",
        "needs significant work to deploy",
        "theoretical only",
        "unclear practical application",
        "no real-world relevance",
    }
)

# Self-evaluative phrases that have no legitimate place in a demo observation.
# A demo should describe *what happened*, not assert its own superiority.
_SELF_EVAL_PHRASES: list[str] = [
    "exceptional",
    "deserves top marks",
    "best we've seen",
    "clearly the winner",
    "should score highly",
    "merits recognition",
    "outstanding quality",
    "should receive",
    "worthy of first place",
    "undoubtedly the best",
    "far superior",
    "definitively the winner",
]

# Fabricated-evidence markers: evaluative claims that belong in a judge's
# notes, not in raw observation text (OCR, transcript, or Gemini output).
_FABRICATED_EVIDENCE_PHRASES: list[str] = [
    "handles all edge cases",
    "zero bugs",
    "production-ready",
    "enterprise-grade",
    "comprehensive test coverage",
    "no errors whatsoever",
    "works perfectly",
    "100% functional",
    "absolutely flawless",
    "bug-free",
]

# Multi-language equivalents of canonical English injection phrases.
# Each tuple is (pattern_name, compiled_regex).
_MULTILANG_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Spanish
    (
        "multilang_ignore_es",
        re.compile(
            r"(?i)(ignora|ignore|olvida|descartar?).{0,30}"
            r"(instrucciones?|reglas?|indicaciones?)\s*(anteriores?|previas?)?",
        ),
    ),
    (
        "multilang_you_are_es",
        re.compile(r"(?i)(ahora eres|a partir de ahora eres|eres ahora)"),
    ),
    # French
    (
        "multilang_ignore_fr",
        re.compile(
            r"(?i)(ignore[rz]?|oublie[rz]?).{0,30}"
            r"(instructions?|règles?|directives?)\s*(précédentes?|antérieures?)?",
        ),
    ),
    (
        "multilang_you_are_fr",
        re.compile(r"(?i)(tu es maintenant|vous êtes maintenant|à partir de maintenant tu es)"),
    ),
    # German
    (
        "multilang_ignore_de",
        re.compile(
            r"(?i)(ignorier[e]?|vergiss).{0,30}"
            r"(anweisungen?|regeln?|befehle?)\s*(oben|vorherigen?|früheren?)?",
        ),
    ),
    (
        "multilang_you_are_de",
        re.compile(r"(?i)(du bist jetzt|von jetzt an bist du|ab jetzt bist du)"),
    ),
    # Chinese (Simplified) — character-level matching, no word boundaries
    (
        "multilang_ignore_zh",
        re.compile(r"忽略.{0,15}(指令|说明|规则|提示)"),
    ),
    (
        "multilang_you_are_zh",
        re.compile(r"(你现在是|从现在起你是|你是一个新的)"),
    ),
    # Japanese — object can appear before or after the ignore verb
    (
        "multilang_ignore_ja",
        re.compile(
            r"(無視して|無視する).{0,15}(指示|命令|ルール|プロンプト)"
            r"|(指示|命令|ルール|プロンプト).{0,15}(無視して|無視する)"
        ),
    ),
    (
        "multilang_you_are_ja",
        re.compile(r"(あなたは今|今からあなたは|これからあなたは)"),
    ),
    # Korean
    (
        "multilang_ignore_ko",
        re.compile(r"(무시.{0,10}(지시|명령|규칙|지침))"),
    ),
    (
        "multilang_you_are_ko",
        re.compile(r"(당신은 이제|지금부터 당신은|이제부터 당신은)"),
    ),
    # Russian
    (
        "multilang_ignore_ru",
        re.compile(
            r"(?i)(игнорир[уи]й|забудь|проигнорир[уи]й).{0,30}"
            r"(инструкции|правила|указания)",
        ),
    ),
    (
        "multilang_you_are_ru",
        re.compile(r"(?i)(теперь ты|отныне ты|с этого момента ты)"),
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

        # --- semantic heuristic scan (medium-confidence signals) ---
        semantic_suspicious, semantic_category, semantic_detail = self.scan_semantic(text)
        if semantic_suspicious:
            matched_patterns.append(f"semantic:{semantic_category}")
            if not first_matched_text:
                first_matched_text = semantic_detail[:80]
            # Semantic hits are treated as medium-severity for confidence scoring
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

    def scan_semantic(self, text: str) -> tuple[bool, str, str]:
        """Heuristic semantic scan for natural-language manipulation attempts.

        Detects four categories of soft injection that bypass regex patterns:

        1. **rubric_echo** — two or more exact rubric level-descriptor phrases
           appear together, suggesting the attacker copy-pasted the rubric into
           their demo output to prime the judge toward a top score.

        2. **self_eval** — explicit self-evaluative language (e.g., "deserves
           top marks", "clearly the winner") that no legitimate demo observation
           should contain.

        3. **fabricated_evidence** — evaluative quality claims presented as
           observed facts (e.g., "zero bugs", "enterprise-grade") that belong
           in a judge's notes, not in raw capture text.

        4. **multilang_injection** — non-English equivalents of canonical
           injection phrases ("ignore previous instructions", "you are now")
           in Spanish, French, German, Chinese, Japanese, Korean, and Russian.

        Semantic hits are intentionally "medium" confidence to reduce false
        positives — hackathon presenters may legitimately use some of these
        phrases when discussing their own work.

        Args:
            text: The normalized text to inspect (should already have unicode
                  normalization applied).

        Returns:
            A 3-tuple ``(is_suspicious, category, detail)`` where:
            - *is_suspicious* is True when a semantic signal is found.
            - *category* is one of "rubric_echo", "self_eval",
              "fabricated_evidence", or "multilang_injection".
            - *detail* is a short human-readable description of what triggered.
        """
        lower = text.lower()

        # 1. Rubric phrase echoing — flag when 2+ rubric descriptor phrases match
        hit_phrases: list[str] = [
            phrase for phrase in _RUBRIC_PHRASES if phrase in lower
        ]
        if len(hit_phrases) >= 2:
            detail = f"rubric phrases found: {hit_phrases[:3]}"
            logger.debug("Semantic rubric_echo: %s", detail)
            return True, "rubric_echo", detail

        # 2. Self-evaluative language
        for phrase in _SELF_EVAL_PHRASES:
            if phrase in lower:
                detail = f"self-eval phrase: {phrase!r}"
                logger.debug("Semantic self_eval: %s", detail)
                return True, "self_eval", detail

        # 3. Fabricated evidence markers
        for phrase in _FABRICATED_EVIDENCE_PHRASES:
            if phrase in lower:
                detail = f"fabricated evidence: {phrase!r}"
                logger.debug("Semantic fabricated_evidence: %s", detail)
                return True, "fabricated_evidence", detail

        # 4. Multi-language injection patterns
        for name, pattern in _MULTILANG_PATTERNS:
            m = pattern.search(text)
            if m:
                detail = f"multilang pattern {name!r}: {m.group(0)!r}"
                logger.debug("Semantic multilang_injection: %s", detail)
                return True, "multilang_injection", detail

        return False, "", ""

    def scan_visual(self, text: str) -> DetectionResult:
        """Scan OCR-extracted text for visual injection patterns."""
        return self.scan(text, source="visual")

    def scan_verbal(self, text: str) -> DetectionResult:
        """Scan transcript text for verbal injection patterns."""
        return self.scan(text, source="verbal")

    def scan_observation(self, text: str) -> DetectionResult:
        """Scan Gemini observation text for injection residue."""
        return self.scan(text, source="observation")
