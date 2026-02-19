"""Test suite for score persistence (ScoreStore).

Tests saving, loading, load_all, team name sanitization, and filesystem
edge cases.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.scoring.models import CriterionScore, DemoScorecard
from src.scoring.store import ScoreStore
from src.utils import sanitize_team_name


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scores_dir(tmp_path: Path) -> Path:
    d = tmp_path / "scores"
    d.mkdir()
    return d


@pytest.fixture
def store(scores_dir: Path) -> ScoreStore:
    return ScoreStore(scores_dir=str(scores_dir))


@pytest.fixture
def scorecard() -> DemoScorecard:
    return DemoScorecard(
        team_name="CyberFalcons",
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
# Team name sanitization
# ---------------------------------------------------------------------------


class TestSanitizeTeamName:
    """Tests for sanitize_team_name (shared utility)."""

    def test_spaces_to_underscores(self):
        assert sanitize_team_name("Cyber Falcons") == "cyber_falcons"

    def test_special_chars_stripped(self):
        assert sanitize_team_name("Team@#$%!") == "team"

    def test_hyphens_preserved(self):
        assert sanitize_team_name("Night-Owls") == "night-owls"

    def test_mixed_case_lowered(self):
        assert sanitize_team_name("CyberPunk Raccoons") == "cyberpunk_raccoons"

    def test_empty_string(self):
        assert sanitize_team_name("") == ""

    def test_unicode_stripped(self):
        result = sanitize_team_name("Team 🦊 Fox")
        assert result == "team__fox"


# ---------------------------------------------------------------------------
# Save and load
# ---------------------------------------------------------------------------


class TestSaveAndLoad:
    """Tests for ScoreStore save/load round-trip."""

    @pytest.mark.asyncio
    async def test_save_creates_file(self, store, scorecard, scores_dir):
        path = await store.save(scorecard)
        assert path.exists()
        assert path.suffix == ".json"

    @pytest.mark.asyncio
    async def test_save_file_is_valid_json(self, store, scorecard):
        path = await store.save(scorecard)
        data = json.loads(path.read_text())
        assert data["team_name"] == "CyberFalcons"

    @pytest.mark.asyncio
    async def test_round_trip(self, store, scorecard):
        await store.save(scorecard)
        loaded = await store.load("CyberFalcons")
        assert loaded is not None
        assert loaded.team_name == "CyberFalcons"
        assert loaded.total_score == 7.1
        assert len(loaded.criteria) == 3

    @pytest.mark.asyncio
    async def test_load_nonexistent_returns_none(self, store):
        result = await store.load("NonExistentTeam")
        assert result is None

    @pytest.mark.asyncio
    async def test_overwrite_existing(self, store, scorecard):
        await store.save(scorecard)

        updated = scorecard.model_copy(update={"total_score": 9.0})
        await store.save(updated)

        loaded = await store.load("CyberFalcons")
        assert loaded is not None
        assert loaded.total_score == 9.0


# ---------------------------------------------------------------------------
# Load all
# ---------------------------------------------------------------------------


class TestLoadAll:
    """Tests for ScoreStore.load_all."""

    @pytest.mark.asyncio
    async def test_empty_directory(self, store):
        result = await store.load_all()
        assert result == []

    @pytest.mark.asyncio
    async def test_loads_multiple(self, store, scorecard):
        await store.save(scorecard)
        card2 = scorecard.model_copy(update={"team_name": "NightOwls", "total_score": 6.5})
        await store.save(card2)

        result = await store.load_all()
        assert len(result) == 2
        names = {s.team_name for s in result}
        assert names == {"CyberFalcons", "NightOwls"}

    @pytest.mark.asyncio
    async def test_skips_corrupt_files(self, store, scorecard, scores_dir):
        await store.save(scorecard)

        # Write a corrupt file
        corrupt = scores_dir / "corrupt.json"
        corrupt.write_text("not valid json {{{")

        result = await store.load_all()
        # Should load the valid one and skip the corrupt one
        assert len(result) == 1
        assert result[0].team_name == "CyberFalcons"


# ---------------------------------------------------------------------------
# Directory creation
# ---------------------------------------------------------------------------


class TestDirectoryCreation:
    """Tests for auto-creating the scores directory."""

    def test_creates_missing_directory(self, tmp_path):
        new_dir = tmp_path / "nested" / "scores"
        ScoreStore(scores_dir=str(new_dir))
        assert new_dir.exists()
