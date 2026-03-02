"""Re-score from cached observations: prompt construction and scoring path.

Loads real observations directly into ScoringEngine, validating prompt
construction and scoring structure for all 15 historical demos. No full
pipeline wiring needed -- tests the scoring engine in isolation.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.scoring.engine import ScoringEngine
from src.scoring.rubric import GENERAL_CRITERIA, TRACK_CRITERIA
from tests.helpers.demo_memory import ALL_DEMOS, DemoMemory, to_sanitized

# ---------------------------------------------------------------------------
# Canned Gemini response for scoring path tests
# ---------------------------------------------------------------------------


def _make_canned_response() -> str:
    """Build a valid scoring JSON response for mock _call_gemini."""
    return json.dumps({
        "criteria": [
            {
                "name": "Technical Execution",
                "score": 8.5,
                "justification": "Strong implementation with clean architecture.",
            },
            {
                "name": "Innovation",
                "score": 7.0,
                "justification": "Novel approach to the problem space.",
            },
            {
                "name": "Demo Quality",
                "score": 6.5,
                "justification": "Solid demo with minor presentation gaps.",
            },
        ],
        "track_bonus": {
            "name": "Originality Factor",
            "score": 7.5,
            "justification": "Creative integration of techniques.",
        },
    })


# ---------------------------------------------------------------------------
# Class 1: Prompt construction (synchronous, no mocks)
# ---------------------------------------------------------------------------


class TestPromptConstructionFromCache:
    """Verify _build_prompt produces correct prompts from real observations."""

    @pytest.mark.parametrize(
        "memory",
        ALL_DEMOS,
        ids=[m.team_name for m in ALL_DEMOS],
    )
    def test_team_name_in_prompt(self, memory: DemoMemory):
        sanitized = to_sanitized(memory)
        prompt = ScoringEngine._build_prompt(
            sanitized, memory.track, GENERAL_CRITERIA, TRACK_CRITERIA
        )
        assert memory.team_name in prompt

    @pytest.mark.parametrize(
        "memory",
        ALL_DEMOS,
        ids=[m.team_name for m in ALL_DEMOS],
    )
    def test_track_in_prompt(self, memory: DemoMemory):
        sanitized = to_sanitized(memory)
        prompt = ScoringEngine._build_prompt(
            sanitized, memory.track, GENERAL_CRITERIA, TRACK_CRITERIA
        )
        assert memory.track in prompt

    @pytest.mark.parametrize(
        "memory",
        ALL_DEMOS,
        ids=[m.team_name for m in ALL_DEMOS],
    )
    def test_observations_present(self, memory: DemoMemory):
        """First 40 chars of each observation appear in prompt."""
        sanitized = to_sanitized(memory)
        prompt = ScoringEngine._build_prompt(
            sanitized, memory.track, GENERAL_CRITERIA, TRACK_CRITERIA
        )
        for obs in memory.observations:
            snippet = obs[:40]
            assert snippet in prompt, (
                f"Observation snippet not found in prompt: {snippet!r}"
            )

    @pytest.mark.parametrize(
        "memory",
        ALL_DEMOS,
        ids=[m.team_name for m in ALL_DEMOS],
    )
    def test_transcripts_present(self, memory: DemoMemory):
        """All transcripts appear in prompt."""
        sanitized = to_sanitized(memory)
        prompt = ScoringEngine._build_prompt(
            sanitized, memory.track, GENERAL_CRITERIA, TRACK_CRITERIA
        )
        for transcript in memory.transcripts:
            assert transcript in prompt, (
                f"Transcript not found in prompt: {transcript[:50]!r}"
            )

    @pytest.mark.parametrize(
        "memory",
        ALL_DEMOS,
        ids=[m.team_name for m in ALL_DEMOS],
    )
    def test_duration_string(self, memory: DemoMemory):
        sanitized = to_sanitized(memory)
        prompt = ScoringEngine._build_prompt(
            sanitized, memory.track, GENERAL_CRITERIA, TRACK_CRITERIA
        )
        expected = f"{memory.demo_duration:.0f}s"
        assert expected in prompt

    @pytest.mark.parametrize(
        "memory",
        ALL_DEMOS,
        ids=[m.team_name for m in ALL_DEMOS],
    )
    def test_injection_count_is_zero(self, memory: DemoMemory):
        """Cached demos have no injection attempts (empty list in SanitizedOutput)."""
        sanitized = to_sanitized(memory)
        prompt = ScoringEngine._build_prompt(
            sanitized, memory.track, GENERAL_CRITERIA, TRACK_CRITERIA
        )
        assert "Injection attempts detected: 0" in prompt

    @pytest.mark.parametrize(
        "memory",
        ALL_DEMOS,
        ids=[m.team_name for m in ALL_DEMOS],
    )
    def test_json_schema_section(self, memory: DemoMemory):
        sanitized = to_sanitized(memory)
        prompt = ScoringEngine._build_prompt(
            sanitized, memory.track, GENERAL_CRITERIA, TRACK_CRITERIA
        )
        assert "JSON" in prompt
        assert '"criteria"' in prompt

    @pytest.mark.parametrize(
        "memory",
        ALL_DEMOS,
        ids=[m.team_name for m in ALL_DEMOS],
    )
    def test_track_bonus_presence(self, memory: DemoMemory):
        """track_bonus appears in prompt iff track has a known criterion."""
        sanitized = to_sanitized(memory)
        prompt = ScoringEngine._build_prompt(
            sanitized, memory.track, GENERAL_CRITERIA, TRACK_CRITERIA
        )
        if memory.track in TRACK_CRITERIA:
            assert "track_bonus" in prompt
        else:
            assert "track_bonus" not in prompt

    @pytest.mark.parametrize(
        "memory",
        ALL_DEMOS,
        ids=[m.team_name for m in ALL_DEMOS],
    )
    def test_rubric_criteria_names(self, memory: DemoMemory):
        sanitized = to_sanitized(memory)
        prompt = ScoringEngine._build_prompt(
            sanitized, memory.track, GENERAL_CRITERIA, TRACK_CRITERIA
        )
        for criterion in GENERAL_CRITERIA:
            assert criterion.name in prompt

    @pytest.mark.parametrize(
        "memory",
        ALL_DEMOS,
        ids=[m.team_name for m in ALL_DEMOS],
    )
    def test_calibration_anchors(self, memory: DemoMemory):
        sanitized = to_sanitized(memory)
        prompt = ScoringEngine._build_prompt(
            sanitized, memory.track, GENERAL_CRITERIA, TRACK_CRITERIA
        )
        assert "9-10" in prompt
        assert "Flawless implementation" in prompt


# ---------------------------------------------------------------------------
# Class 2: Scoring from cache (async, mocked _call_gemini)
# ---------------------------------------------------------------------------


class TestScoringFromCache:
    """Verify ScoringEngine.score() with real observations and canned LLM."""

    @pytest.mark.parametrize(
        "memory",
        ALL_DEMOS,
        ids=[m.team_name for m in ALL_DEMOS],
    )
    async def test_valid_scorecard_returned(self, memory: DemoMemory):
        engine = ScoringEngine(api_key="test-key")
        sanitized = to_sanitized(memory)
        canned = _make_canned_response()

        with patch.object(engine, "_call_gemini", new=AsyncMock(return_value=canned)):
            scorecard = await engine.score(sanitized, memory.track)

        assert scorecard.team_name == memory.team_name
        assert scorecard.track == memory.track
        assert len(scorecard.criteria) == 3
        for criterion in scorecard.criteria:
            assert 0.0 <= criterion.score <= 10.0

    @pytest.mark.parametrize(
        "memory",
        ALL_DEMOS,
        ids=[m.team_name for m in ALL_DEMOS],
    )
    async def test_total_matches_weighted_sum(self, memory: DemoMemory):
        """Total is Python-computed weighted sum, not LLM-provided."""
        engine = ScoringEngine(api_key="test-key")
        sanitized = to_sanitized(memory)
        canned = _make_canned_response()

        with patch.object(engine, "_call_gemini", new=AsyncMock(return_value=canned)):
            scorecard = await engine.score(sanitized, memory.track)

        expected_base = sum(c.score * c.weight for c in scorecard.criteria)
        if scorecard.track_bonus:
            expected_base += scorecard.track_bonus.score * scorecard.track_bonus.weight
        assert scorecard.total_score == round(expected_base, 1)

    @pytest.mark.parametrize(
        "memory",
        ALL_DEMOS,
        ids=[m.team_name for m in ALL_DEMOS],
    )
    async def test_weights_from_rubric(self, memory: DemoMemory):
        """Weights come from GENERAL_CRITERIA, not the LLM response."""
        engine = ScoringEngine(api_key="test-key")
        sanitized = to_sanitized(memory)
        canned = _make_canned_response()

        with patch.object(engine, "_call_gemini", new=AsyncMock(return_value=canned)):
            scorecard = await engine.score(sanitized, memory.track)

        weight_map = {c.name: c.weight for c in scorecard.criteria}
        assert weight_map["Technical Execution"] == 0.40
        assert weight_map["Innovation"] == 0.30
        assert weight_map["Demo Quality"] == 0.30

    @pytest.mark.parametrize(
        "memory",
        ALL_DEMOS,
        ids=[m.team_name for m in ALL_DEMOS],
    )
    async def test_not_fallback_scorecard(self, memory: DemoMemory):
        """With canned valid JSON, should not produce the 5.0 fallback."""
        engine = ScoringEngine(api_key="test-key")
        sanitized = to_sanitized(memory)
        canned = _make_canned_response()

        with patch.object(engine, "_call_gemini", new=AsyncMock(return_value=canned)):
            scorecard = await engine.score(sanitized, memory.track)

        assert scorecard.total_score != 5.0
