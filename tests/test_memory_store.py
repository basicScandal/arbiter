"""Test suite for memory persistence (MemoryStore).

Tests saving, loading, load_all, team name sanitization, and filesystem
edge cases. Mirrors the ScoreStore test patterns.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.memory.models import DemoMemory
from src.memory.store import MemoryStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def obs_dir(tmp_path: Path) -> Path:
    d = tmp_path / "observations"
    d.mkdir()
    return d


@pytest.fixture
def store(obs_dir: Path) -> MemoryStore:
    return MemoryStore(observations_dir=str(obs_dir))


@pytest.fixture
def memory() -> DemoMemory:
    return DemoMemory(
        team_name="CyberFalcons",
        track="ROGUE::AGENT",
        observations=["Built a packet analysis tool", "Used Scapy effectively"],
        transcripts=["We built this in 48 hours"],
        injection_attempts=0,
        demo_duration=180.0,
        stored_at=1000.0,
    )


# ---------------------------------------------------------------------------
# Team name sanitization
# ---------------------------------------------------------------------------


class TestSanitizeTeamName:
    """Tests for MemoryStore._sanitize_team_name."""

    def test_spaces_to_underscores(self):
        assert MemoryStore._sanitize_team_name("Cyber Falcons") == "cyber_falcons"

    def test_special_chars_stripped(self):
        assert MemoryStore._sanitize_team_name("Team@#$%!") == "team"

    def test_hyphens_preserved(self):
        assert MemoryStore._sanitize_team_name("Night-Owls") == "night-owls"

    def test_mixed_case_lowered(self):
        assert MemoryStore._sanitize_team_name("CyberPunk Raccoons") == "cyberpunk_raccoons"

    def test_empty_string(self):
        assert MemoryStore._sanitize_team_name("") == ""

    def test_unicode_stripped(self):
        result = MemoryStore._sanitize_team_name("Team 🦊 Fox")
        assert result == "team__fox"


# ---------------------------------------------------------------------------
# Save and load
# ---------------------------------------------------------------------------


class TestSaveAndLoad:
    """Tests for MemoryStore save/load round-trip."""

    @pytest.mark.asyncio
    async def test_save_creates_file(self, store, memory, obs_dir):
        path = await store.save(memory)
        assert path.exists()
        assert path.suffix == ".json"

    @pytest.mark.asyncio
    async def test_save_file_is_valid_json(self, store, memory):
        path = await store.save(memory)
        data = json.loads(path.read_text())
        assert data["team_name"] == "CyberFalcons"

    @pytest.mark.asyncio
    async def test_round_trip(self, store, memory):
        await store.save(memory)
        loaded = await store.load("CyberFalcons")
        assert loaded is not None
        assert loaded.team_name == "CyberFalcons"
        assert loaded.track == "ROGUE::AGENT"
        assert loaded.demo_duration == 180.0
        assert len(loaded.observations) == 2
        assert loaded.injection_attempts == 0

    @pytest.mark.asyncio
    async def test_load_nonexistent_returns_none(self, store):
        result = await store.load("NonExistentTeam")
        assert result is None

    @pytest.mark.asyncio
    async def test_overwrite_existing(self, store, memory):
        await store.save(memory)

        updated = memory.model_copy(update={"injection_attempts": 3})
        await store.save(updated)

        loaded = await store.load("CyberFalcons")
        assert loaded is not None
        assert loaded.injection_attempts == 3

    @pytest.mark.asyncio
    async def test_preserves_observations_and_transcripts(self, store, memory):
        await store.save(memory)
        loaded = await store.load("CyberFalcons")
        assert loaded is not None
        assert loaded.observations == ["Built a packet analysis tool", "Used Scapy effectively"]
        assert loaded.transcripts == ["We built this in 48 hours"]


# ---------------------------------------------------------------------------
# Load all
# ---------------------------------------------------------------------------


class TestLoadAll:
    """Tests for MemoryStore.load_all."""

    @pytest.mark.asyncio
    async def test_empty_directory(self, store):
        result = await store.load_all()
        assert result == []

    @pytest.mark.asyncio
    async def test_loads_multiple(self, store, memory):
        await store.save(memory)
        mem2 = memory.model_copy(update={"team_name": "NightOwls", "demo_duration": 120.0})
        await store.save(mem2)

        result = await store.load_all()
        assert len(result) == 2
        names = {m.team_name for m in result}
        assert names == {"CyberFalcons", "NightOwls"}

    @pytest.mark.asyncio
    async def test_skips_corrupt_files(self, store, memory, obs_dir):
        await store.save(memory)

        corrupt = obs_dir / "corrupt.json"
        corrupt.write_text("not valid json {{{")

        result = await store.load_all()
        assert len(result) == 1
        assert result[0].team_name == "CyberFalcons"


# ---------------------------------------------------------------------------
# Directory creation
# ---------------------------------------------------------------------------


class TestDirectoryCreation:
    """Tests for auto-creating the observations directory."""

    def test_creates_missing_directory(self, tmp_path):
        new_dir = tmp_path / "nested" / "observations"
        store = MemoryStore(observations_dir=str(new_dir))
        assert new_dir.exists()
