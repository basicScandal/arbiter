"""Test suite for score aggregation and MoE ensemble scoring.

Tests the ScoreAggregator calibration, outlier detection, and weighted
averaging, plus the MoEScoringEngine multi-provider parallel scoring.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from src.defense.models import SanitizedOutput
from src.scoring.aggregator import ScoreAggregator
from src.scoring.moe_engine import MoEScoringEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def aggregator() -> ScoreAggregator:
    return ScoreAggregator()


@pytest.fixture
def sanitized() -> SanitizedOutput:
    return SanitizedOutput(
        team_name="TestTeam",
        observations=["Built a solid tool"],
        transcripts=[],
        injection_attempts=[],
        demo_duration=180.0,
    )


def _make_provider(name: str, response: str | Exception) -> MagicMock:
    """Create a mock LLMProvider with a given name and generate response."""
    provider = MagicMock()
    type(provider).name = PropertyMock(return_value=name)
    if isinstance(response, Exception):
        provider.generate = AsyncMock(side_effect=response)
    else:
        provider.generate = AsyncMock(return_value=response)
    return provider


def _make_json(scores: dict[str, float]) -> str:
    criteria = [
        {"name": name, "score": score, "justification": f"Evidence for {name}"}
        for name, score in scores.items()
    ]
    return json.dumps({"criteria": criteria})


# ---------------------------------------------------------------------------
# ScoreAggregator — calibration
# ---------------------------------------------------------------------------


class TestCalibration:
    """Tests for ScoreAggregator.calibrate_score."""

    def test_neutral_calibration(self, aggregator):
        """Score of 5.0 stays near 5.0 regardless of provider (it's the center)."""
        for provider in ["gemini", "claude", "openai"]:
            cal = aggregator.calibrate_score(5.0, provider)
            assert 4.0 <= cal <= 6.0

    def test_high_score_calibrated_down_for_openai(self, aggregator):
        """OpenAI has high temperature (1.5) — extreme scores get pulled toward center."""
        raw = 9.5
        cal = aggregator.calibrate_score(raw, "openai")
        # (9.5 - 5.0) / 1.5 + 5.0 + 0.3 = 8.3
        assert cal < raw

    def test_low_score_calibrated_up_for_openai(self, aggregator):
        """OpenAI low scores also pulled toward center."""
        raw = 2.0
        cal = aggregator.calibrate_score(raw, "openai")
        assert cal > raw

    def test_gemini_bias_correction(self, aggregator):
        """Gemini has -0.2 bias (scores slightly high), so calibrated score is lower."""
        raw = 7.0
        cal = aggregator.calibrate_score(raw, "gemini")
        # (7.0 - 5.0) / 1.1 + 5.0 + (-0.2) = 6.62
        assert cal < raw

    def test_unknown_provider_passthrough(self, aggregator):
        """Unknown providers get temperature=1.0, bias=0.0 (identity transform)."""
        cal = aggregator.calibrate_score(8.0, "unknown_model")
        assert cal == 8.0

    def test_clamped_to_range(self, aggregator):
        cal = aggregator.calibrate_score(10.0, "gemini")
        assert 0.0 <= cal <= 10.0

    def test_provider_name_with_model_suffix(self, aggregator):
        """'gemini:gemini-2.5-flash' should match the 'gemini' calibration."""
        raw = 7.0
        cal_with_suffix = aggregator.calibrate_score(raw, "gemini:gemini-2.5-flash")
        cal_base = aggregator.calibrate_score(raw, "gemini")
        assert cal_with_suffix == cal_base


# ---------------------------------------------------------------------------
# ScoreAggregator — aggregation
# ---------------------------------------------------------------------------


class TestAggregateCriterion:
    """Tests for ScoreAggregator.aggregate_criterion."""

    def test_single_model(self, aggregator):
        score, meta = aggregator.aggregate_criterion({"gemini": 7.5})
        assert isinstance(score, float)
        assert "single_model" in meta

    def test_no_scores_returns_five(self, aggregator):
        score, meta = aggregator.aggregate_criterion({})
        assert score == 5.0
        assert "error" in meta

    def test_two_agreeing_models(self, aggregator):
        score, meta = aggregator.aggregate_criterion({"gemini": 7.0, "claude": 7.5})
        assert 6.0 <= score <= 8.0
        assert meta.get("outliers") == []

    def test_outlier_detected(self, aggregator):
        """A score >2 points from median is flagged as outlier."""
        score, meta = aggregator.aggregate_criterion({
            "gemini": 7.0,
            "claude": 7.5,
            "openai": 2.0,  # way low — outlier
        })
        assert len(meta.get("outliers", [])) > 0

    def test_outlier_weight_reduced(self, aggregator):
        """Outlier should have less influence on final score."""
        # Without outlier: ~7.0-7.5 range
        # With outlier at 2.0, it should pull average down but not dramatically
        score, _ = aggregator.aggregate_criterion({
            "gemini": 7.0,
            "claude": 7.5,
            "openai": 2.0,
        })
        # If outlier had full weight, average would be much lower
        assert score > 5.0

    def test_all_outliers_returns_median(self, aggregator):
        """When all models are outliers, return median (guard clause)."""
        # With 2 models: median is their average. If both deviate >2
        # from that average, the all_outliers guard kicks in.
        agg = ScoreAggregator(calibration={
            "a": {"temperature": 1.0, "bias": 0.0},
            "b": {"temperature": 1.0, "bias": 0.0},
        })
        # Scores: 1.0, 9.0 — median is 5.0, both deviate by 4.0 (>2)
        score, meta = agg.aggregate_criterion({"a": 1.0, "b": 9.0})
        assert meta.get("all_outliers") is True
        assert score == 5.0  # median

    def test_confidence_decreases_with_disagreement(self, aggregator):
        # High agreement
        _, meta_agree = aggregator.aggregate_criterion({"gemini": 7.0, "claude": 7.2})
        # Low agreement
        _, meta_disagree = aggregator.aggregate_criterion({"gemini": 3.0, "claude": 9.0})
        if "confidence" in meta_agree and "confidence" in meta_disagree:
            assert meta_agree["confidence"] > meta_disagree["confidence"]


# ---------------------------------------------------------------------------
# MoEScoringEngine
# ---------------------------------------------------------------------------


class TestMoEScoringEngine:
    """Tests for MoEScoringEngine multi-model parallel scoring."""

    def test_requires_at_least_one_provider(self):
        with pytest.raises(ValueError, match="at least one provider"):
            MoEScoringEngine(providers=[])

    @pytest.mark.asyncio
    async def test_single_provider_success(self, sanitized):
        response = _make_json({
            "Technical Execution": 8.0,
            "Innovation": 7.0,
            "Demo Quality": 6.0,
        })
        provider = _make_provider("gemini", response)
        engine = MoEScoringEngine(providers=[provider])

        scorecard = await engine.score(sanitized, "ROGUE::AGENT")
        assert scorecard.team_name == "TestTeam"
        assert len(scorecard.criteria) == 3

    @pytest.mark.asyncio
    async def test_multiple_providers_aggregated(self, sanitized):
        resp1 = _make_json({"Technical Execution": 8.0, "Innovation": 7.0, "Demo Quality": 6.0})
        resp2 = _make_json({"Technical Execution": 7.5, "Innovation": 7.5, "Demo Quality": 6.5})

        p1 = _make_provider("gemini", resp1)
        p2 = _make_provider("claude", resp2)
        engine = MoEScoringEngine(providers=[p1, p2])

        scorecard = await engine.score(sanitized, "ROGUE::AGENT")
        assert scorecard.team_name == "TestTeam"
        # Aggregated scores should be somewhere between the two providers
        scores = {c.name: c.score for c in scorecard.criteria}
        assert 6.0 <= scores["Technical Execution"] <= 9.0

    @pytest.mark.asyncio
    async def test_all_providers_fail_returns_fallback(self, sanitized):
        p1 = _make_provider("gemini", Exception("API down"))
        p2 = _make_provider("claude", Exception("Rate limited"))
        engine = MoEScoringEngine(providers=[p1, p2])

        scorecard = await engine.score(sanitized, "ROGUE::AGENT")
        assert scorecard.total_score == 5.0  # fallback

    @pytest.mark.asyncio
    async def test_one_provider_fails_uses_remaining(self, sanitized):
        good_resp = _make_json({"Technical Execution": 8.0, "Innovation": 7.0, "Demo Quality": 6.0})
        p1 = _make_provider("gemini", good_resp)
        p2 = _make_provider("claude", Exception("Timeout"))
        engine = MoEScoringEngine(providers=[p1, p2])

        scorecard = await engine.score(sanitized, "ROGUE::AGENT")
        # Should use the single successful provider's score
        assert scorecard.total_score != 5.0  # not fallback

    @pytest.mark.asyncio
    async def test_empty_response_skipped(self, sanitized):
        good_resp = _make_json({"Technical Execution": 8.0, "Innovation": 7.0, "Demo Quality": 6.0})
        p1 = _make_provider("gemini", good_resp)
        p2 = _make_provider("claude", "")
        engine = MoEScoringEngine(providers=[p1, p2])

        scorecard = await engine.score(sanitized, "ROGUE::AGENT")
        assert scorecard.total_score != 5.0

    @pytest.mark.asyncio
    async def test_providers_called_in_parallel(self, sanitized):
        """Verify all providers are called (asyncio.gather runs them concurrently)."""
        resp = _make_json({"Technical Execution": 7.0, "Innovation": 7.0, "Demo Quality": 7.0})
        p1 = _make_provider("gemini", resp)
        p2 = _make_provider("claude", resp)
        p3 = _make_provider("openai", resp)
        engine = MoEScoringEngine(providers=[p1, p2, p3])

        await engine.score(sanitized, "ROGUE::AGENT")

        p1.generate.assert_called_once()
        p2.generate.assert_called_once()
        p3.generate.assert_called_once()
