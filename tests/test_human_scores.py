"""Test suite for human judge score integration.

Tests HumanScore model validation, HumanScoreStore persistence,
and blend_scores logic (no human scores, with human scores, nonexistent team).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.scoring.human import (
    AI_WEIGHT,
    HUMAN_WEIGHT,
    HumanScore,
    HumanScoreStore,
    blend_scores,
)
from src.scoring.models import CriterionScore, DemoScorecard

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def human_scores_dir(tmp_path: Path) -> Path:
    d = tmp_path / "human_scores"
    d.mkdir()
    return d


@pytest.fixture
def store(human_scores_dir: Path) -> HumanScoreStore:
    return HumanScoreStore(scores_dir=str(human_scores_dir))


@pytest.fixture
def sample_scorecard() -> DemoScorecard:
    return DemoScorecard(
        team_name="TestTeam",
        track="ROGUE::AGENT",
        criteria=[
            CriterionScore(name="Technical Execution", score=8.0, weight=0.40, justification="Solid"),
            CriterionScore(name="Innovation", score=7.0, weight=0.30, justification="Novel"),
            CriterionScore(name="Demo Quality", score=6.0, weight=0.30, justification="Good"),
        ],
        track_bonus=None,
        total_score=7.1,
        scored_at=1000.0,
    )


# ---------------------------------------------------------------------------
# 1. HumanScore model validation
# ---------------------------------------------------------------------------


class TestHumanScoreModel:
    """Tests for HumanScore pydantic model validation."""

    def test_valid_score(self):
        score = HumanScore(
            judge_name="Alice",
            team_name="TestTeam",
            total_score=8.5,
            notes="Great demo",
            submitted_at=1000.0,
        )
        assert score.judge_name == "Alice"
        assert score.team_name == "TestTeam"
        assert score.total_score == 8.5
        assert score.notes == "Great demo"

    def test_score_at_zero_is_valid(self):
        score = HumanScore(judge_name="Bob", team_name="Team", total_score=0.0)
        assert score.total_score == 0.0

    def test_score_at_ten_is_valid(self):
        score = HumanScore(judge_name="Carol", team_name="Team", total_score=10.0)
        assert score.total_score == 10.0

    def test_score_above_ten_is_rejected(self):
        with pytest.raises(ValidationError):
            HumanScore(judge_name="Dave", team_name="Team", total_score=10.1)

    def test_score_below_zero_is_rejected(self):
        with pytest.raises(ValidationError):
            HumanScore(judge_name="Eve", team_name="Team", total_score=-0.1)

    def test_defaults_for_optional_fields(self):
        score = HumanScore(judge_name="Frank", team_name="Team", total_score=5.0)
        assert score.notes == ""
        assert score.submitted_at == 0.0


# ---------------------------------------------------------------------------
# 2. HumanScoreStore save and load
# ---------------------------------------------------------------------------


class TestHumanScoreStore:
    """Tests for HumanScoreStore persistence."""

    @pytest.mark.asyncio
    async def test_save_creates_file(self, store: HumanScoreStore, human_scores_dir: Path):
        score = HumanScore(judge_name="Alice", team_name="TestTeam", total_score=8.0)
        path = await store.save(score)
        assert path.exists()
        assert path.suffix == ".json"

    @pytest.mark.asyncio
    async def test_save_file_is_valid_json(self, store: HumanScoreStore):
        score = HumanScore(judge_name="Alice", team_name="TestTeam", total_score=8.0)
        path = await store.save(score)
        data = json.loads(path.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["judge_name"] == "Alice"
        assert data[0]["team_name"] == "TestTeam"

    @pytest.mark.asyncio
    async def test_load_returns_saved_score(self, store: HumanScoreStore):
        score = HumanScore(judge_name="Alice", team_name="TestTeam", total_score=8.0)
        await store.save(score)

        loaded = await store.load("TestTeam")
        assert len(loaded) == 1
        assert loaded[0].judge_name == "Alice"
        assert loaded[0].total_score == 8.0

    @pytest.mark.asyncio
    async def test_load_nonexistent_team_returns_empty_list(self, store: HumanScoreStore):
        result = await store.load("NonExistentTeam")
        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_judges_per_team(self, store: HumanScoreStore):
        """Save 2 scores for the same team; load returns both."""
        score1 = HumanScore(judge_name="Alice", team_name="TestTeam", total_score=8.0)
        score2 = HumanScore(judge_name="Bob", team_name="TestTeam", total_score=6.0)

        await store.save(score1)
        await store.save(score2)

        loaded = await store.load("TestTeam")
        assert len(loaded) == 2
        judge_names = {s.judge_name for s in loaded}
        assert judge_names == {"Alice", "Bob"}

    @pytest.mark.asyncio
    async def test_team_name_is_sanitized_for_storage(self, store: HumanScoreStore, human_scores_dir: Path):
        """Team names with spaces are sanitized to valid filenames."""
        score = HumanScore(judge_name="Alice", team_name="Cyber Falcons", total_score=7.5)
        path = await store.save(score)
        assert path.name == "cyber_falcons.json"

    @pytest.mark.asyncio
    async def test_load_all_teams(self, store: HumanScoreStore):
        """load_all_teams returns dict keyed by team name."""
        score1 = HumanScore(judge_name="Alice", team_name="TeamA", total_score=8.0)
        score2 = HumanScore(judge_name="Bob", team_name="TeamB", total_score=6.0)

        await store.save(score1)
        await store.save(score2)

        all_teams = await store.load_all_teams()
        assert "TeamA" in all_teams
        assert "TeamB" in all_teams
        assert all_teams["TeamA"][0].judge_name == "Alice"
        assert all_teams["TeamB"][0].judge_name == "Bob"

    def test_directory_is_created_if_missing(self, tmp_path: Path):
        new_dir = tmp_path / "nested" / "human_scores"
        HumanScoreStore(scores_dir=str(new_dir))
        assert new_dir.exists()


# ---------------------------------------------------------------------------
# 3. blend_scores logic
# ---------------------------------------------------------------------------


class TestBlendScores:
    """Tests for the blend_scores async function."""

    @pytest.mark.asyncio
    async def test_blend_scores_nonexistent_team_returns_none(self, tmp_path: Path):
        """blend_scores returns None when no AI scorecard exists."""
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir()
        human_dir = tmp_path / "human_scores"
        human_dir.mkdir()

        with (
            patch("src.scoring.human.ScoreStore") as MockScoreStore,
            patch("src.scoring.human.HumanScoreStore") as MockHumanStore,
        ):
            mock_ai = AsyncMock()
            mock_ai.load.return_value = None
            MockScoreStore.return_value = mock_ai

            mock_human = AsyncMock()
            mock_human.load.return_value = []
            MockHumanStore.return_value = mock_human

            result = await blend_scores("NonExistentTeam")
            assert result is None

    @pytest.mark.asyncio
    async def test_blend_scores_no_human_scores_returns_ai_as_is(
        self, sample_scorecard: DemoScorecard
    ):
        """blend_scores with no human scores returns AI score as blended_score."""
        with (
            patch("src.scoring.human.ScoreStore") as MockScoreStore,
            patch("src.scoring.human.HumanScoreStore") as MockHumanStore,
        ):
            mock_ai = AsyncMock()
            mock_ai.load.return_value = sample_scorecard
            MockScoreStore.return_value = mock_ai

            mock_human = AsyncMock()
            mock_human.load.return_value = []
            MockHumanStore.return_value = mock_human

            result = await blend_scores("TestTeam")

        assert result is not None
        assert result.team_name == "TestTeam"
        assert result.ai_score == 7.1
        assert result.human_score == 0.0
        assert result.blended_score == 7.1
        assert result.ai_weight == 1.0
        assert result.human_weight == 0.0
        assert result.human_judges == []

    @pytest.mark.asyncio
    async def test_blend_scores_applies_70_30_blend(self, sample_scorecard: DemoScorecard):
        """blend_scores with human scores applies AI_WEIGHT/HUMAN_WEIGHT blend."""
        human_scores = [
            HumanScore(judge_name="Alice", team_name="TestTeam", total_score=9.0),
            HumanScore(judge_name="Bob", team_name="TestTeam", total_score=7.0),
        ]

        with (
            patch("src.scoring.human.ScoreStore") as MockScoreStore,
            patch("src.scoring.human.HumanScoreStore") as MockHumanStore,
        ):
            mock_ai = AsyncMock()
            mock_ai.load.return_value = sample_scorecard
            MockScoreStore.return_value = mock_ai

            mock_human = AsyncMock()
            mock_human.load.return_value = human_scores
            MockHumanStore.return_value = mock_human

            result = await blend_scores("TestTeam")

        assert result is not None
        # avg human = (9.0 + 7.0) / 2 = 8.0
        expected_avg_human = 8.0
        # blended = 0.7 * 7.1 + 0.3 * 8.0 = 4.97 + 2.4 = 7.37
        expected_blended = round(AI_WEIGHT * 7.1 + HUMAN_WEIGHT * expected_avg_human, 2)

        assert result.ai_score == 7.1
        assert result.human_score == expected_avg_human
        assert result.blended_score == expected_blended
        assert result.ai_weight == AI_WEIGHT
        assert result.human_weight == HUMAN_WEIGHT
        assert len(result.human_judges) == 2

    @pytest.mark.asyncio
    async def test_blend_scores_single_human_judge(self, sample_scorecard: DemoScorecard):
        """blend_scores with a single human judge uses their score directly."""
        human_scores = [
            HumanScore(judge_name="Alice", team_name="TestTeam", total_score=10.0),
        ]

        with (
            patch("src.scoring.human.ScoreStore") as MockScoreStore,
            patch("src.scoring.human.HumanScoreStore") as MockHumanStore,
        ):
            mock_ai = AsyncMock()
            mock_ai.load.return_value = sample_scorecard
            MockScoreStore.return_value = mock_ai

            mock_human = AsyncMock()
            mock_human.load.return_value = human_scores
            MockHumanStore.return_value = mock_human

            result = await blend_scores("TestTeam")

        assert result is not None
        expected_blended = round(AI_WEIGHT * 7.1 + HUMAN_WEIGHT * 10.0, 2)
        assert result.human_score == 10.0
        assert result.blended_score == expected_blended

    @pytest.mark.asyncio
    async def test_blend_scores_preserves_ai_criteria_and_track(
        self, sample_scorecard: DemoScorecard
    ):
        """blend_scores result includes the original AI criteria and track info."""
        with (
            patch("src.scoring.human.ScoreStore") as MockScoreStore,
            patch("src.scoring.human.HumanScoreStore") as MockHumanStore,
        ):
            mock_ai = AsyncMock()
            mock_ai.load.return_value = sample_scorecard
            MockScoreStore.return_value = mock_ai

            mock_human = AsyncMock()
            mock_human.load.return_value = []
            MockHumanStore.return_value = mock_human

            result = await blend_scores("TestTeam")

        assert result is not None
        assert result.track == "ROGUE::AGENT"
        assert len(result.ai_criteria) == 3
        assert result.track_bonus is None

    @pytest.mark.asyncio
    async def test_blend_scores_blended_at_is_recent(self, sample_scorecard: DemoScorecard):
        """blend_scores sets blended_at to a recent timestamp."""
        before = time.time()

        with (
            patch("src.scoring.human.ScoreStore") as MockScoreStore,
            patch("src.scoring.human.HumanScoreStore") as MockHumanStore,
        ):
            mock_ai = AsyncMock()
            mock_ai.load.return_value = sample_scorecard
            MockScoreStore.return_value = mock_ai

            mock_human = AsyncMock()
            mock_human.load.return_value = []
            MockHumanStore.return_value = mock_human

            result = await blend_scores("TestTeam")

        after = time.time()
        assert result is not None
        assert before <= result.blended_at <= after
