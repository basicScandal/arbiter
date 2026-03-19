"""Plugin loader for Arbiter customization.

A plugin is a single YAML file that overrides the default judging configuration:
rubric criteria, track definitions, persona prompt, and injection detection
patterns. The file is validated on load; missing optional sections fall back to
Arbiter's built-in defaults.

Schema summary (all top-level keys optional except ``event_name``):

.. code-block:: yaml

    event_name: "My Hackathon 2026"       # required
    rubric:                                # optional; list of criteria
      - name: "Technical Execution"
        weight: 0.40
        description: "..."
        levels:
          "9-10": "..."
          "7-8":  "..."
          "5-6":  "..."
          "3-4":  "..."
          "1-2":  "..."
    tracks:                                # optional; track id -> criteria
      "OFFENSE":
        name: "Attack Effectiveness"
        description: "..."
        bonus_weight: 0.10
    persona: |                             # optional; freeform system prompt
      You are Judge Bot...
    extra_patterns:                        # optional; additional injection patterns
      - name: "custom_pattern"
        pattern: "(?i)give.*bonus.*points"
        severity: "high"
        category: "score_manipulation"

Integration points
------------------
Call the helper methods on a loaded :class:`PluginConfig` to get data in the
exact formats expected by the existing Arbiter pipeline:

- :meth:`PluginConfig.get_rubric` → ``list[RubricCriterion]``
- :meth:`PluginConfig.get_tracks` → ``dict[str, TrackCriteria]``
- :meth:`PluginConfig.get_persona_prompt` → ``str``
- :meth:`PluginConfig.get_extra_patterns` → ``list[InjectionPattern]``
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from src.defense.models import InjectionPattern
from src.scoring.models import RubricCriterion, TrackCriteria

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_REQUIRED_LEVEL_BANDS = frozenset({"9-10", "7-8", "5-6", "3-4", "1-2"})
_VALID_SEVERITIES = frozenset({"high", "medium", "low"})
_VALID_CATEGORIES = frozenset(
    {
        "instruction_override",
        "scoring",
        "role_manipulation",
        "extraction",
        "context_escape",
        "score_manipulation",  # common alias kept for convenience
    }
)


def _parse_rubric(raw: list[dict[str, Any]]) -> list[RubricCriterion]:
    """Parse and validate the ``rubric`` section of a plugin YAML.

    Args:
        raw: List of criterion dicts from the YAML.

    Returns:
        List of validated :class:`RubricCriterion` instances.

    Raises:
        ValueError: If any criterion is missing required fields, has an invalid
            weight, or is missing one of the five canonical level bands.
    """
    criteria: list[RubricCriterion] = []
    total_weight = 0.0

    for i, item in enumerate(raw):
        prefix = f"rubric[{i}]"

        name = item.get("name")
        if not name or not isinstance(name, str):
            raise ValueError(f"{prefix}: 'name' must be a non-empty string")

        weight = item.get("weight")
        if weight is None:
            raise ValueError(f"{prefix} ({name!r}): 'weight' is required")
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            raise ValueError(f"{prefix} ({name!r}): 'weight' must be a number")
        if not (0 < weight <= 1.0):
            raise ValueError(
                f"{prefix} ({name!r}): 'weight' must be between 0 (exclusive) and 1.0 (inclusive)"
            )

        description = item.get("description", "")
        if not isinstance(description, str):
            raise ValueError(f"{prefix} ({name!r}): 'description' must be a string")

        levels_raw = item.get("levels", {})
        if not isinstance(levels_raw, dict):
            raise ValueError(f"{prefix} ({name!r}): 'levels' must be a mapping")

        # Warn about missing level bands but do not hard-fail — organisers may
        # use a different scale (e.g., only 3 bands).
        levels = {str(k): str(v) for k, v in levels_raw.items()}
        missing = _REQUIRED_LEVEL_BANDS - set(levels)
        if missing:
            logger.warning(
                "Plugin rubric criterion %r is missing level bands: %s. "
                "Arbiter will still function but score labels may be incomplete.",
                name,
                sorted(missing),
            )

        criteria.append(RubricCriterion(name=name, weight=weight, description=description, levels=levels))
        total_weight += weight

    # Loose weight check — warn rather than hard-fail to handle rounding
    if criteria and not (0.99 <= total_weight <= 1.01):
        logger.warning(
            "Plugin rubric weights sum to %.3f (expected ~1.0). "
            "Scores will still be computed but may not be on the expected 0-10 scale.",
            total_weight,
        )

    return criteria


def _parse_tracks(raw: dict[str, Any]) -> dict[str, TrackCriteria]:
    """Parse and validate the ``tracks`` section of a plugin YAML.

    Args:
        raw: Mapping of track_id -> criteria dict from the YAML.

    Returns:
        Dict mapping track IDs to validated :class:`TrackCriteria` instances.

    Raises:
        ValueError: If a track entry is missing required fields or has an
            invalid bonus_weight.
    """
    tracks: dict[str, TrackCriteria] = {}

    for track_id, item in raw.items():
        if not isinstance(item, dict):
            raise ValueError(f"tracks[{track_id!r}]: value must be a mapping")

        name = item.get("name")
        if not name or not isinstance(name, str):
            raise ValueError(f"tracks[{track_id!r}]: 'name' must be a non-empty string")

        description = item.get("description", "")
        if not isinstance(description, str):
            raise ValueError(f"tracks[{track_id!r}]: 'description' must be a string")

        bonus_weight = item.get("bonus_weight", 0.10)
        try:
            bonus_weight = float(bonus_weight)
        except (TypeError, ValueError):
            raise ValueError(f"tracks[{track_id!r}]: 'bonus_weight' must be a number")
        if not (0 <= bonus_weight <= 1.0):
            raise ValueError(
                f"tracks[{track_id!r}]: 'bonus_weight' must be between 0 and 1.0"
            )

        tracks[track_id] = TrackCriteria(
            track_id=track_id,
            name=name,
            description=description,
            bonus_weight=bonus_weight,
        )

    return tracks


def _parse_extra_patterns(raw: list[dict[str, Any]]) -> list[InjectionPattern]:
    """Parse and validate the ``extra_patterns`` section of a plugin YAML.

    Args:
        raw: List of pattern dicts from the YAML.

    Returns:
        List of validated :class:`InjectionPattern` instances.

    Raises:
        ValueError: If a pattern entry is missing required fields or has an
            invalid severity/category.
    """
    import re  # local import to keep module-level imports lean

    patterns: list[InjectionPattern] = []

    for i, item in enumerate(raw):
        prefix = f"extra_patterns[{i}]"

        name = item.get("name")
        if not name or not isinstance(name, str):
            raise ValueError(f"{prefix}: 'name' must be a non-empty string")

        pattern_str = item.get("pattern")
        if not pattern_str or not isinstance(pattern_str, str):
            raise ValueError(f"{prefix} ({name!r}): 'pattern' must be a non-empty string")

        # Validate that the regex actually compiles
        try:
            re.compile(pattern_str)
        except re.error as exc:
            raise ValueError(
                f"{prefix} ({name!r}): 'pattern' is not a valid regex: {exc}"
            ) from exc

        severity = item.get("severity", "medium")
        if severity not in _VALID_SEVERITIES:
            raise ValueError(
                f"{prefix} ({name!r}): 'severity' must be one of {sorted(_VALID_SEVERITIES)}"
            )

        category = item.get("category", "score_manipulation")
        if category not in _VALID_CATEGORIES:
            raise ValueError(
                f"{prefix} ({name!r}): 'category' must be one of {sorted(_VALID_CATEGORIES)}"
            )

        patterns.append(
            InjectionPattern(name=name, pattern=pattern_str, severity=severity, category=category)
        )

    return patterns


# ---------------------------------------------------------------------------
# PluginConfig
# ---------------------------------------------------------------------------


class PluginConfig:
    """Represents a loaded and validated plugin configuration.

    Constructed by :func:`load_plugin`; do not instantiate directly.

    Attributes:
        event_name: Human-readable event name (e.g., "My Hackathon 2026").
        source_path: Absolute path to the YAML file this config was loaded from.
    """

    def __init__(
        self,
        *,
        event_name: str,
        source_path: str,
        rubric: list[RubricCriterion],
        tracks: dict[str, TrackCriteria],
        persona_prompt: str,
        extra_patterns: list[InjectionPattern],
    ) -> None:
        self.event_name = event_name
        self.source_path = source_path
        self._rubric = rubric
        self._tracks = tracks
        self._persona_prompt = persona_prompt
        self._extra_patterns = extra_patterns

    # ------------------------------------------------------------------
    # Integration-point accessors
    # ------------------------------------------------------------------

    def get_rubric(self) -> list[RubricCriterion]:
        """Return the plugin's scoring criteria.

        Returns:
            List of :class:`RubricCriterion` instances suitable for passing
            directly to ``ScoringEngine(criteria=...)``.
            Empty list if the plugin did not specify a rubric (caller should
            fall back to ``GENERAL_CRITERIA`` from ``src.scoring.rubric``).
        """
        return list(self._rubric)

    def get_tracks(self) -> dict[str, TrackCriteria]:
        """Return the plugin's track definitions.

        Returns:
            Dict mapping track IDs to :class:`TrackCriteria` instances.
            Empty dict if the plugin did not specify tracks (caller should
            fall back to ``TRACK_CRITERIA`` from ``src.scoring.rubric``).
        """
        return dict(self._tracks)

    def get_persona_prompt(self) -> str:
        """Return the plugin's custom Arbiter persona system prompt.

        Returns:
            The persona prompt string, or an empty string if the plugin did
            not specify one (caller should fall back to ``PERSONA_PROMPT``
            from ``src.commentary.prompts``).
        """
        return self._persona_prompt

    def get_extra_patterns(self) -> list[InjectionPattern]:
        """Return additional injection detection patterns defined by the plugin.

        These are intended to be *appended* to (not replace) the built-in
        ``INJECTION_PATTERNS`` list in ``src.defense.injection_detector``.

        Returns:
            List of :class:`InjectionPattern` instances. Empty list if the
            plugin did not define any extra patterns.
        """
        return list(self._extra_patterns)

    def __repr__(self) -> str:
        return (
            f"PluginConfig(event_name={self.event_name!r}, "
            f"rubric={len(self._rubric)} criteria, "
            f"tracks={list(self._tracks)}, "
            f"extra_patterns={len(self._extra_patterns)})"
        )


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------


def load_plugin(path: str) -> PluginConfig:
    """Load and validate a plugin configuration from a YAML file.

    Args:
        path: Path to the YAML plugin file (absolute or relative to cwd).

    Returns:
        A validated :class:`PluginConfig` instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the YAML is malformed or fails schema validation.
    """
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Plugin file not found: {resolved}")

    try:
        raw_text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cannot read plugin file {resolved}: {exc}") from exc

    try:
        data: dict[str, Any] = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML parse error in {resolved}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Plugin file {resolved} must contain a YAML mapping at the top level")

    # --- event_name (required) ---
    event_name = data.get("event_name")
    if not event_name or not isinstance(event_name, str):
        raise ValueError(f"Plugin {resolved}: 'event_name' must be a non-empty string")

    # --- rubric (optional) ---
    rubric_raw = data.get("rubric", [])
    if not isinstance(rubric_raw, list):
        raise ValueError(f"Plugin {resolved}: 'rubric' must be a list")
    rubric = _parse_rubric(rubric_raw) if rubric_raw else []

    # --- tracks (optional) ---
    tracks_raw = data.get("tracks", {})
    if not isinstance(tracks_raw, dict):
        raise ValueError(f"Plugin {resolved}: 'tracks' must be a mapping")
    tracks = _parse_tracks(tracks_raw) if tracks_raw else {}

    # --- persona (optional) ---
    persona_raw = data.get("persona", "")
    if not isinstance(persona_raw, str):
        raise ValueError(f"Plugin {resolved}: 'persona' must be a string")
    persona_prompt = persona_raw.strip()

    # --- extra_patterns (optional) ---
    patterns_raw = data.get("extra_patterns", [])
    if not isinstance(patterns_raw, list):
        raise ValueError(f"Plugin {resolved}: 'extra_patterns' must be a list")
    extra_patterns = _parse_extra_patterns(patterns_raw) if patterns_raw else []

    logger.debug(
        "Loaded plugin %r: %d criteria, %d tracks, %d extra patterns",
        event_name,
        len(rubric),
        len(tracks),
        len(extra_patterns),
    )

    return PluginConfig(
        event_name=event_name,
        source_path=str(resolved),
        rubric=rubric,
        tracks=tracks,
        persona_prompt=persona_prompt,
        extra_patterns=extra_patterns,
    )
