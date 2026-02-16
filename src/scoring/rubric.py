"""Rubric definitions for NEBULA:FOG 2026 scoring.

Provides configurable rubric criteria for general and extended evaluation,
plus track-specific criteria for all four challenge tracks.

Default weights match SCORE-01 requirement:
  Technical Execution 40%, Innovation 30%, Demo Quality 30% (3 criteria).
EXTENDED_CRITERIA provides a 4-criterion variant if the official rubric
uses 4 dimensions. The rubric is configurable -- ScoringEngine accepts
optional criteria parameter to override the default.
"""

from __future__ import annotations

from src.scoring.models import RubricCriterion, TrackCriteria


# ---------------------------------------------------------------------------
# General criteria (SCORE-01 default: 3 criteria, 40/30/30)
# ---------------------------------------------------------------------------

GENERAL_CRITERIA: list[RubricCriterion] = [
    RubricCriterion(
        name="Technical Execution",
        weight=0.40,
        description=(
            "Implementation quality, functionality, complexity, "
            "code correctness, edge case handling"
        ),
        levels={
            "9-10": "Flawless implementation, production-quality, handles edge cases",
            "7-8": "Solid implementation with minor gaps",
            "5-6": "Functional but rough, obvious shortcuts",
            "3-4": "Partially working, significant bugs",
            "1-2": "Barely functional or broken",
        },
    ),
    RubricCriterion(
        name="Innovation",
        weight=0.30,
        description=(
            "AI x Security novelty, creative approaches, original thinking"
        ),
        levels={
            "9-10": "Groundbreaking novel approach",
            "7-8": "Clearly innovative with unique angle",
            "5-6": "Some novelty but mostly established techniques",
            "3-4": "Incremental or derivative",
            "1-2": "No discernible innovation",
        },
    ),
    RubricCriterion(
        name="Demo Quality",
        weight=0.30,
        description=(
            "Clear explanation, working live demo, effective presentation, "
            "compelling narrative"
        ),
        levels={
            "9-10": (
                "Flawless live demo, masterful explanation, compelling narrative"
            ),
            "7-8": "Solid demo with good explanation, minor hiccups",
            "5-6": "Demo works but explanation unclear or rushed",
            "3-4": "Demo partially works, confusing presentation",
            "1-2": "Demo fails or no meaningful demonstration",
        },
    ),
]


# ---------------------------------------------------------------------------
# Extended criteria (4-criterion variant matching nebulafog.ai website)
# ---------------------------------------------------------------------------

EXTENDED_CRITERIA: list[RubricCriterion] = [
    RubricCriterion(
        name="Technical Execution",
        weight=0.30,
        description=(
            "Implementation quality, functionality, complexity, "
            "code correctness, edge case handling"
        ),
        levels={
            "9-10": "Flawless implementation, production-quality, handles edge cases",
            "7-8": "Solid implementation with minor gaps",
            "5-6": "Functional but rough, obvious shortcuts",
            "3-4": "Partially working, significant bugs",
            "1-2": "Barely functional or broken",
        },
    ),
    RubricCriterion(
        name="Innovation",
        weight=0.25,
        description=(
            "AI x Security novelty, creative approaches, original thinking"
        ),
        levels={
            "9-10": "Groundbreaking novel approach",
            "7-8": "Clearly innovative with unique angle",
            "5-6": "Some novelty but mostly established techniques",
            "3-4": "Incremental or derivative",
            "1-2": "No discernible innovation",
        },
    ),
    RubricCriterion(
        name="Impact",
        weight=0.20,
        description=(
            "Real-world relevance, deployability, solves actual problems"
        ),
        levels={
            "9-10": (
                "Immediately deployable, addresses critical real-world need"
            ),
            "7-8": "Strong real-world potential with clear use case",
            "5-6": "Moderate relevance, needs significant work to deploy",
            "3-4": "Theoretical only, unclear practical application",
            "1-2": "No real-world relevance",
        },
    ),
    RubricCriterion(
        name="Demo Quality",
        weight=0.25,
        description=(
            "Clear explanation, working live demo, effective presentation, "
            "compelling narrative"
        ),
        levels={
            "9-10": (
                "Flawless live demo, masterful explanation, compelling narrative"
            ),
            "7-8": "Solid demo with good explanation, minor hiccups",
            "5-6": "Demo works but explanation unclear or rushed",
            "3-4": "Demo partially works, confusing presentation",
            "1-2": "Demo fails or no meaningful demonstration",
        },
    ),
]


# ---------------------------------------------------------------------------
# Track-specific criteria for all four NEBULA:FOG tracks
# ---------------------------------------------------------------------------

TRACK_CRITERIA: dict[str, TrackCriteria] = {
    "SHADOW::VECTOR": TrackCriteria(
        track_id="SHADOW::VECTOR",
        name="Attack Effectiveness",
        description=(
            "Novelty and effectiveness of attack approach, "
            "responsible disclosure consideration"
        ),
        bonus_weight=0.10,
    ),
    "SENTINEL::MESH": TrackCriteria(
        track_id="SENTINEL::MESH",
        name="Defense Robustness",
        description=(
            "Real-world applicability of defense, detection accuracy, "
            "hardening effectiveness"
        ),
        bonus_weight=0.10,
    ),
    "ZERO::PROOF": TrackCriteria(
        track_id="ZERO::PROOF",
        name="Privacy Guarantees",
        description=(
            "Cryptographic soundness, privacy preservation completeness, "
            "verification integrity"
        ),
        bonus_weight=0.10,
    ),
    "ROGUE::AGENT": TrackCriteria(
        track_id="ROGUE::AGENT",
        name="Originality Factor",
        description=(
            "Ambition relative to time constraint, exploration of "
            "uncharted territory"
        ),
        bonus_weight=0.10,
    ),
}
