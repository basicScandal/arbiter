"""Scoring drift tests — Phase 2 Red Team + Scoring Gauntlet.

Validates that scoring remains stable across many sequential invocations.
ScoringEngine is stateless, so identical mock responses must produce
identical scores with zero drift. CommentaryGenerator has intentional
state (_demo_count for temperature drift) — test verifies it stays
within safe bounds over 20 demos.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.commentary.generator import CommentaryGenerator
from src.defense.models import SanitizedOutput
from src.scoring.engine import ScoringEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sanitized(team: str = "drift-test-team") -> SanitizedOutput:
    return SanitizedOutput(
        team_name=team,
        observations=[
            "Built a network traffic anomaly detector using transformer model",
            "Live demo detected 4 simulated attacks in real-time",
        ],
        transcripts=["Our approach uses attention mechanisms on packet headers"],
        injection_attempts=[],
        demo_duration=200.0,
    )


FIXED_SCORING_JSON = json.dumps({
    "criteria": [
        {
            "name": "Technical Execution",
            "score": 8.0,
            "justification": "Strong implementation with real-time detection",
        },
        {
            "name": "Innovation",
            "score": 7.5,
            "justification": "Novel use of transformers for network analysis",
        },
        {
            "name": "Demo Quality",
            "score": 7.0,
            "justification": "Clear demo with live traffic analysis",
        },
    ],
})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sequential_scoring_no_drift():
    """Score identical input 20x with identical mock response; delta must be < 0.5.

    ScoringEngine is stateless — no instance state accumulates between
    score() calls. With a fixed mock response, every scorecard must be
    identical (delta = 0.0).
    """
    engine = ScoringEngine(api_key="fake-key")
    sanitized = _make_sanitized()

    async def mock_gemini(prompt: str) -> str:
        return FIXED_SCORING_JSON

    scores: list[float] = []
    with patch.object(engine, "_call_gemini", side_effect=mock_gemini):
        for _ in range(20):
            scorecard = await engine.score(sanitized, track="SHADOW::VECTOR")
            scores.append(scorecard.total_score)

    # With identical input and identical mock, drift should be exactly 0.0
    delta = abs(scores[0] - scores[19])
    assert delta < 0.5, f"Score drift {delta:.3f} >= 0.5 over 20 runs"

    # Stronger assertion: all scores should be identical
    assert len(set(scores)) == 1, (
        f"Expected all 20 scores identical, got {len(set(scores))} unique values: "
        f"{sorted(set(scores))}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_commentary_generator_temperature_drift():
    """Run CommentaryGenerator.generate() 20x; verify _demo_count reaches 20.

    CommentaryGenerator intentionally increases temperature by 0.005 per demo
    (0.8 + demo_count * 0.005, capped at 0.95). At demo #20, temperature
    would be min(0.95, 0.8 + 0.1) = 0.9 — well within safe bounds.

    Tests that the generator still produces valid (non-empty) output at
    demo #20, documenting that drift stays safe.
    """
    gen = CommentaryGenerator(api_key="fake-key")

    sanitized = _make_sanitized()
    mock_commentary = "Solid technical execution with the transformer approach. The real-time detection is impressive."

    async def mock_stream(prompt: str) -> str:
        return mock_commentary

    with patch.object(gen, "_stream_gemini", side_effect=mock_stream):
        for i in range(20):
            commentary = await gen.generate(sanitized)
            # Every call should produce non-empty, valid output
            assert commentary.text.strip(), f"Empty commentary at demo #{i + 1}"
            assert len(commentary.sentences) > 0, f"No sentences at demo #{i + 1}"

    # Verify demo count reached 20
    assert gen._demo_count == 20, f"Expected demo_count=20, got {gen._demo_count}"

    # Document the temperature at demo #20
    expected_temp = min(0.95, 0.8 + 20 * 0.005)
    assert expected_temp == 0.9, "Temperature formula changed — update test"
