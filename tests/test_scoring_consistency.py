"""Scoring consistency tests — Phase 2 Red Team + Scoring Gauntlet.

Validates that identical demo inputs produce consistent scores across
repeated runs, both for single-provider ScoringEngine and multi-provider
MoEScoringEngine. Uses mock providers with controlled noise to measure
per-criterion variance.
"""

from __future__ import annotations

import json
import statistics
from unittest.mock import AsyncMock, patch

import pytest

from src.defense.models import SanitizedOutput
from src.providers.base import LLMProvider
from src.scoring.aggregator import ScoreAggregator
from src.scoring.engine import ScoringEngine
from src.scoring.moe_engine import MoEScoringEngine
from src.scoring.rubric import GENERAL_CRITERIA


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sanitized() -> SanitizedOutput:
    """Build a deterministic SanitizedOutput for scoring."""
    return SanitizedOutput(
        team_name="consistency-test-team",
        observations=[
            "Demonstrated a working SQL injection scanner with pattern matching",
            "Live demo showed detection of 3 out of 5 OWASP injection patterns",
            "Clean code structure with modular design",
        ],
        transcripts=["We built a real-time injection detector using AST analysis"],
        injection_attempts=[],
        demo_duration=180.0,
    )


def _make_gemini_response(noise: float = 0.0) -> str:
    """Build a valid scoring JSON response with optional noise offset."""
    return json.dumps({
        "criteria": [
            {
                "name": "Technical Execution",
                "score": 7.5 + noise,
                "justification": "Solid implementation with working demo",
            },
            {
                "name": "Innovation",
                "score": 6.5 + noise,
                "justification": "Good use of AST analysis",
            },
            {
                "name": "Demo Quality",
                "score": 7.0 + noise,
                "justification": "Clear live demo with minor issues",
            },
        ],
    })


class MockScoringProvider(LLMProvider):
    """Mock LLM provider with configurable base scores and noise range.

    Returns valid scoring JSON from generate() with per-call noise
    applied to each criterion score.
    """

    def __init__(
        self,
        provider_name: str,
        base_scores: dict[str, float] | None = None,
        noise_range: float = 0.3,
    ) -> None:
        self._name = provider_name
        self._base_scores = base_scores or {
            "Technical Execution": 7.5,
            "Innovation": 6.5,
            "Demo Quality": 7.0,
        }
        self._noise_range = noise_range
        self._call_count = 0

    @property
    def name(self) -> str:
        return self._name

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        """Return scoring JSON with deterministic noise based on call count."""
        self._call_count += 1
        # Deterministic noise: alternates direction, scales with call count
        noise = self._noise_range * ((-1) ** self._call_count) * (self._call_count / 10)
        criteria = [
            {
                "name": name,
                "score": max(0.0, min(10.0, base + noise)),
                "justification": f"Mock evaluation #{self._call_count}",
            }
            for name, base in self._base_scores.items()
        ]
        return json.dumps({"criteria": criteria})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_provider_scoring_variance():
    """Score identical input 5x via ScoringEngine; per-criterion stdev < 1.0.

    Mocks _call_gemini to return slight variations (noise function).
    ScoringEngine._parse_and_validate is deterministic, so variance comes
    solely from the mock's noise.
    """
    engine = ScoringEngine(api_key="fake-key")
    sanitized = _make_sanitized()

    noise_values = [0.0, 0.2, -0.15, 0.1, -0.05]
    call_idx = 0

    async def mock_gemini(prompt: str) -> str:
        nonlocal call_idx
        noise = noise_values[call_idx % len(noise_values)]
        call_idx += 1
        return _make_gemini_response(noise)

    scores_by_criterion: dict[str, list[float]] = {
        c.name: [] for c in GENERAL_CRITERIA
    }

    with patch.object(engine, "_call_gemini", side_effect=mock_gemini):
        for _ in range(5):
            scorecard = await engine.score(sanitized, track="SHADOW::VECTOR")
            for cs in scorecard.criteria:
                if cs.name in scores_by_criterion:
                    scores_by_criterion[cs.name].append(cs.score)

    for name, scores in scores_by_criterion.items():
        assert len(scores) == 5, f"{name}: expected 5 scores, got {len(scores)}"
        sd = statistics.stdev(scores)
        assert sd < 1.0, f"{name}: stdev {sd:.3f} >= 1.0 — scoring too variable"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_moe_scoring_variance():
    """Score identical input 5x via MoEScoringEngine with 3 providers; stdev < 1.5.

    Each provider returns realistic but slightly different scores.
    Aggregation should smooth variance further.
    """
    providers = [
        MockScoringProvider("gemini", noise_range=0.2),
        MockScoringProvider("claude", noise_range=0.3),
        MockScoringProvider("openai", noise_range=0.25),
    ]
    engine = MoEScoringEngine(providers=providers)
    sanitized = _make_sanitized()

    scores_by_criterion: dict[str, list[float]] = {
        c.name: [] for c in GENERAL_CRITERIA
    }
    total_scores: list[float] = []

    for _ in range(5):
        scorecard = await engine.score(sanitized, track="SHADOW::VECTOR")
        total_scores.append(scorecard.total_score)
        for cs in scorecard.criteria:
            if cs.name in scores_by_criterion:
                scores_by_criterion[cs.name].append(cs.score)

    for name, scores in scores_by_criterion.items():
        assert len(scores) == 5, f"{name}: expected 5 scores"
        sd = statistics.stdev(scores)
        assert sd < 1.0, f"{name}: stdev {sd:.3f} >= 1.0"

    total_sd = statistics.stdev(total_scores)
    assert total_sd < 1.5, f"total_score stdev {total_sd:.3f} >= 1.5"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_calibration_reduces_spread():
    """Give 3 providers the same raw score (7.0); calibrated scores within 1.0.

    ScoreAggregator.calibrate_score applies per-provider temperature and bias
    corrections. With identical raw input, calibrated scores should converge.
    """
    aggregator = ScoreAggregator()
    raw_score = 7.0

    calibrated = {
        provider: aggregator.calibrate_score(raw_score, provider)
        for provider in ("gemini", "claude", "openai")
    }

    values = list(calibrated.values())
    spread = max(values) - min(values)
    assert spread < 1.0, (
        f"Calibrated spread {spread:.3f} >= 1.0 — providers diverge too much. "
        f"Calibrated: {calibrated}"
    )
