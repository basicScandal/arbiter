"""Test suite for the post-event data export module.

Tests export_event_data and export_team_data for correct structure,
data aggregation, optional sections, and missing-data resilience.
Uses tmp_path and monkeypatch to redirect data directories.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src.reports.export import (
    EventExport,
    TeamExport,
    export_event_data,
    export_team_data,
)
from src.scoring.models import CriterionScore, DemoScorecard

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_scorecard(
    *,
    team_name: str = "CyberFalcons",
    track: str = "ROGUE::AGENT",
    total_score: float = 7.5,
    scored_at: float = 1_700_000_000.0,
) -> DemoScorecard:
    """Build a minimal DemoScorecard for testing."""
    return DemoScorecard(
        team_name=team_name,
        track=track,
        criteria=[
            CriterionScore(
                name="Technical Execution",
                score=8.0,
                weight=0.40,
                justification="Solid.",
            ),
            CriterionScore(
                name="Innovation",
                score=7.0,
                weight=0.30,
                justification="Novel.",
            ),
            CriterionScore(
                name="Demo Quality",
                score=7.0,
                weight=0.30,
                justification="Clear.",
            ),
        ],
        track_bonus=None,
        total_score=total_score,
        scored_at=scored_at,
    )


async def _write_scorecard(scorecard: DemoScorecard, scores_dir: Path) -> None:
    """Write a scorecard JSON file via ScoreStore."""
    from src.scoring.store import ScoreStore

    store = ScoreStore(scores_dir=str(scores_dir))
    await store.save(scorecard)


def _redirect_export_dirs(monkeypatch, tmp_path: Path) -> dict[str, Path]:
    """Redirect all module-level Path constants in src.reports.export to tmp_path."""
    import src.reports.export as export_mod

    scores_dir = tmp_path / "scores"
    observations_dir = tmp_path / "observations"
    commentary_dir = tmp_path / "commentary"
    human_scores_dir = tmp_path / "human_scores"
    audit_log = tmp_path / "audit.jsonl"
    deliberation_dir = tmp_path / "replay" / "deliberation"

    monkeypatch.setattr(export_mod, "SCORES_DIR", scores_dir)
    monkeypatch.setattr(export_mod, "OBSERVATIONS_DIR", observations_dir)
    monkeypatch.setattr(export_mod, "COMMENTARY_DIR", commentary_dir)
    monkeypatch.setattr(export_mod, "HUMAN_SCORES_DIR", human_scores_dir)
    monkeypatch.setattr(export_mod, "AUDIT_LOG", audit_log)
    monkeypatch.setattr(export_mod, "DELIBERATION_DIR", deliberation_dir)

    # Create directories so ScoreStore doesn't fail on mkdir
    scores_dir.mkdir(parents=True, exist_ok=True)
    observations_dir.mkdir(parents=True, exist_ok=True)
    commentary_dir.mkdir(parents=True, exist_ok=True)
    human_scores_dir.mkdir(parents=True, exist_ok=True)
    deliberation_dir.mkdir(parents=True, exist_ok=True)

    return {
        "scores": scores_dir,
        "observations": observations_dir,
        "commentary": commentary_dir,
        "human_scores": human_scores_dir,
        "audit_log": audit_log,
        "deliberation": deliberation_dir,
    }


# ---------------------------------------------------------------------------
# Tests: export_event_data — empty state
# ---------------------------------------------------------------------------


class TestExportEventDataEmpty:
    """Tests for export_event_data when no data files exist."""

    @pytest.mark.asyncio
    async def test_empty_returns_event_export_with_no_teams(
        self, tmp_path: Path, monkeypatch
    ):
        """With no scorecards, teams list is empty."""
        _redirect_export_dirs(monkeypatch, tmp_path)

        result = await export_event_data()

        assert isinstance(result, EventExport)
        assert result.teams == []
        assert result.team_count == 0

    @pytest.mark.asyncio
    async def test_empty_returns_correct_event_name(self, tmp_path: Path, monkeypatch):
        """Event name is always 'NEBULA:FOG 2026'."""
        _redirect_export_dirs(monkeypatch, tmp_path)

        result = await export_event_data()

        assert result.event_name == "NEBULA:FOG 2026"

    @pytest.mark.asyncio
    async def test_empty_exported_at_is_recent(self, tmp_path: Path, monkeypatch):
        """exported_at is a recent Unix timestamp."""
        _redirect_export_dirs(monkeypatch, tmp_path)

        before = time.time()
        result = await export_event_data()
        after = time.time()

        assert before <= result.exported_at <= after

    @pytest.mark.asyncio
    async def test_empty_audit_log_is_empty_without_flag(
        self, tmp_path: Path, monkeypatch
    ):
        """audit_log is empty when include_audit=False (default)."""
        _redirect_export_dirs(monkeypatch, tmp_path)

        result = await export_event_data(include_audit=False)

        assert result.audit_log == []

    @pytest.mark.asyncio
    async def test_empty_deliberation_is_none(self, tmp_path: Path, monkeypatch):
        """deliberation is None when no deliberation result file exists."""
        _redirect_export_dirs(monkeypatch, tmp_path)

        result = await export_event_data()

        assert result.deliberation is None


# ---------------------------------------------------------------------------
# Tests: export_event_data — with scorecard data
# ---------------------------------------------------------------------------


class TestExportEventDataWithScorecard:
    """Tests for export_event_data when scorecard data is present."""

    @pytest.mark.asyncio
    async def test_single_team_returns_correct_structure(
        self, tmp_path: Path, monkeypatch
    ):
        """One scorecard produces one TeamExport with correct fields."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="NightOwls", total_score=8.0)
        await _write_scorecard(sc, dirs["scores"])

        result = await export_event_data()

        assert result.team_count == 1
        assert len(result.teams) == 1
        team = result.teams[0]
        assert isinstance(team, TeamExport)
        assert team.team_name == "NightOwls"
        assert team.track == "ROGUE::AGENT"
        assert team.ai_score == 8.0

    @pytest.mark.asyncio
    async def test_scorecard_field_is_populated(self, tmp_path: Path, monkeypatch):
        """scorecard dict is included in the team export."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="Phantoms")
        await _write_scorecard(sc, dirs["scores"])

        result = await export_event_data()

        team = result.teams[0]
        assert team.scorecard is not None
        assert team.scorecard["team_name"] == "Phantoms"
        assert "criteria" in team.scorecard
        assert "total_score" in team.scorecard

    @pytest.mark.asyncio
    async def test_teams_sorted_by_score_descending(self, tmp_path: Path, monkeypatch):
        """Teams are ordered highest score first."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)

        sc_a = make_scorecard(team_name="TeamA", total_score=6.0)
        sc_b = make_scorecard(team_name="TeamB", total_score=9.0)
        sc_c = make_scorecard(team_name="TeamC", total_score=7.5)
        for sc in [sc_a, sc_b, sc_c]:
            await _write_scorecard(sc, dirs["scores"])

        result = await export_event_data()

        scores = [t.ai_score for t in result.teams]
        assert scores == sorted(scores, reverse=True)
        assert result.teams[0].team_name == "TeamB"

    @pytest.mark.asyncio
    async def test_team_count_matches_teams_length(self, tmp_path: Path, monkeypatch):
        """team_count always equals len(teams)."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)

        for i in range(3):
            sc = make_scorecard(team_name=f"Team{i}", total_score=float(i + 5))
            await _write_scorecard(sc, dirs["scores"])

        result = await export_event_data()

        assert result.team_count == len(result.teams) == 3

    @pytest.mark.asyncio
    async def test_commentary_loaded_when_file_exists(self, tmp_path: Path, monkeypatch):
        """commentary dict is loaded from commentary/<team>.json when it exists."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="AlphaTeam")
        await _write_scorecard(sc, dirs["scores"])

        commentary_data = {
            "team_name": "AlphaTeam",
            "text": "Outstanding performance.",
            "sentences": ["Outstanding performance."],
            "emotion_map": {},
            "generated_at": 1_700_000_000.0,
        }
        (dirs["commentary"] / "alphateam.json").write_text(json.dumps(commentary_data))

        result = await export_event_data()

        team = result.teams[0]
        assert team.commentary is not None
        assert team.commentary["text"] == "Outstanding performance."

    @pytest.mark.asyncio
    async def test_commentary_is_none_when_file_missing(
        self, tmp_path: Path, monkeypatch
    ):
        """commentary is None when no commentary file exists for the team."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="GhostTeam")
        await _write_scorecard(sc, dirs["scores"])

        result = await export_event_data()

        assert result.teams[0].commentary is None

    @pytest.mark.asyncio
    async def test_observations_loaded_when_file_exists(
        self, tmp_path: Path, monkeypatch
    ):
        """observations dict is loaded when include_observations=True (default)."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="DataDragons")
        await _write_scorecard(sc, dirs["scores"])

        obs_data = {
            "team_name": "DataDragons",
            "track": "ROGUE::AGENT",
            "observations": ["Used prompt injection", "Evaded filter"],
            "transcripts": [],
            "injection_attempts": 2,
            "demo_duration": 300.0,
            "stored_at": 1_700_000_000.0,
        }
        (dirs["observations"] / "datadragons.json").write_text(json.dumps(obs_data))

        result = await export_event_data()

        team = result.teams[0]
        assert team.observations is not None
        assert team.observations["team_name"] == "DataDragons"
        assert len(team.observations["observations"]) == 2

    @pytest.mark.asyncio
    async def test_human_scores_loaded_when_file_exists(
        self, tmp_path: Path, monkeypatch
    ):
        """human_scores list is populated from human_scores/<team>.json."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="BioHackers")
        await _write_scorecard(sc, dirs["scores"])

        human_data = [
            {"judge_name": "Alice", "team_name": "BioHackers", "total_score": 8.5, "notes": "", "submitted_at": 1_700_000_000.0},
            {"judge_name": "Bob", "team_name": "BioHackers", "total_score": 7.0, "notes": "Good", "submitted_at": 1_700_000_001.0},
        ]
        (dirs["human_scores"] / "biohackers.json").write_text(json.dumps(human_data))

        result = await export_event_data()

        team = result.teams[0]
        assert len(team.human_scores) == 2
        judge_names = {s["judge_name"] for s in team.human_scores}
        assert judge_names == {"Alice", "Bob"}

    @pytest.mark.asyncio
    async def test_human_scores_empty_when_file_missing(
        self, tmp_path: Path, monkeypatch
    ):
        """human_scores is an empty list when no human score file exists."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="SoloTeam")
        await _write_scorecard(sc, dirs["scores"])

        result = await export_event_data()

        assert result.teams[0].human_scores == []

    @pytest.mark.asyncio
    async def test_deliberation_loaded_when_result_exists(
        self, tmp_path: Path, monkeypatch
    ):
        """deliberation dict is populated from deliberation/result.json when it exists."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="QuickTeam")
        await _write_scorecard(sc, dirs["scores"])

        delib_data = {"winner": "QuickTeam", "rationale": "Best overall."}
        (dirs["deliberation"] / "result.json").write_text(json.dumps(delib_data))

        result = await export_event_data()

        assert result.deliberation is not None
        assert result.deliberation["winner"] == "QuickTeam"


# ---------------------------------------------------------------------------
# Tests: export_event_data — include_audit flag
# ---------------------------------------------------------------------------


class TestExportEventDataAuditLog:
    """Tests for the include_audit parameter."""

    @pytest.mark.asyncio
    async def test_include_audit_true_loads_audit_entries(
        self, tmp_path: Path, monkeypatch
    ):
        """include_audit=True loads all JSONL entries from the audit log."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)

        audit_entries = [
            {"action": "start", "team_name": "TeamX", "timestamp": 1_700_000_000.0},
            {"action": "stop", "team_name": "TeamX", "timestamp": 1_700_000_300.0},
        ]
        audit_log_path = dirs["audit_log"]
        audit_log_path.write_text(
            "\n".join(json.dumps(e) for e in audit_entries) + "\n"
        )

        result = await export_event_data(include_audit=True)

        assert len(result.audit_log) == 2
        assert result.audit_log[0]["action"] == "start"
        assert result.audit_log[1]["action"] == "stop"

    @pytest.mark.asyncio
    async def test_include_audit_false_skips_audit(self, tmp_path: Path, monkeypatch):
        """include_audit=False (default) leaves audit_log empty even when file exists."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)

        audit_entries = [{"action": "start", "team_name": "TeamY"}]
        dirs["audit_log"].write_text(json.dumps(audit_entries[0]) + "\n")

        result = await export_event_data(include_audit=False)

        assert result.audit_log == []

    @pytest.mark.asyncio
    async def test_include_audit_true_empty_file_returns_empty_list(
        self, tmp_path: Path, monkeypatch
    ):
        """include_audit=True with an empty audit file returns empty audit_log."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        dirs["audit_log"].write_text("")

        result = await export_event_data(include_audit=True)

        assert result.audit_log == []

    @pytest.mark.asyncio
    async def test_include_audit_true_file_missing_returns_empty_list(
        self, tmp_path: Path, monkeypatch
    ):
        """include_audit=True with no audit file returns empty audit_log gracefully."""
        _redirect_export_dirs(monkeypatch, tmp_path)
        # audit_log file is not created — should not raise

        result = await export_event_data(include_audit=True)

        assert result.audit_log == []


# ---------------------------------------------------------------------------
# Tests: export_event_data — include_observations flag
# ---------------------------------------------------------------------------


class TestExportEventDataObservations:
    """Tests for the include_observations parameter."""

    @pytest.mark.asyncio
    async def test_include_observations_false_skips_observations(
        self, tmp_path: Path, monkeypatch
    ):
        """include_observations=False leaves observations as None even when file exists."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="SilentTeam")
        await _write_scorecard(sc, dirs["scores"])

        obs_data = {"team_name": "SilentTeam", "observations": ["X"], "transcripts": []}
        (dirs["observations"] / "silentteam.json").write_text(json.dumps(obs_data))

        result = await export_event_data(include_observations=False)

        assert result.teams[0].observations is None

    @pytest.mark.asyncio
    async def test_include_observations_true_loads_observations(
        self, tmp_path: Path, monkeypatch
    ):
        """include_observations=True (default) loads observations from file."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="VerboseTeam")
        await _write_scorecard(sc, dirs["scores"])

        obs_data = {"team_name": "VerboseTeam", "observations": ["Obs1"], "transcripts": []}
        (dirs["observations"] / "verboseteam.json").write_text(json.dumps(obs_data))

        result = await export_event_data(include_observations=True)

        assert result.teams[0].observations is not None
        assert result.teams[0].observations["observations"] == ["Obs1"]


# ---------------------------------------------------------------------------
# Tests: export_team_data
# ---------------------------------------------------------------------------


class TestExportTeamData:
    """Tests for export_team_data (single-team export)."""

    @pytest.mark.asyncio
    async def test_nonexistent_team_returns_none(self, tmp_path: Path, monkeypatch):
        """export_team_data returns None when no scorecard exists for the team."""
        _redirect_export_dirs(monkeypatch, tmp_path)

        result = await export_team_data("NoSuchTeam")

        assert result is None

    @pytest.mark.asyncio
    async def test_existing_team_returns_team_export(self, tmp_path: Path, monkeypatch):
        """export_team_data returns a TeamExport with correct fields."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="Cosmos", total_score=8.5)
        await _write_scorecard(sc, dirs["scores"])

        result = await export_team_data("Cosmos")

        assert result is not None
        assert isinstance(result, TeamExport)
        assert result.team_name == "Cosmos"
        assert result.track == "ROGUE::AGENT"
        assert result.ai_score == 8.5

    @pytest.mark.asyncio
    async def test_team_export_scorecard_populated(self, tmp_path: Path, monkeypatch):
        """export_team_data includes the full scorecard dict."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="Nebulae")
        await _write_scorecard(sc, dirs["scores"])

        result = await export_team_data("Nebulae")

        assert result is not None
        assert result.scorecard is not None
        assert result.scorecard["team_name"] == "Nebulae"
        assert "criteria" in result.scorecard

    @pytest.mark.asyncio
    async def test_team_export_loads_commentary(self, tmp_path: Path, monkeypatch):
        """export_team_data loads commentary when the file exists."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="RiftRiders")
        await _write_scorecard(sc, dirs["scores"])

        commentary_data = {
            "team_name": "RiftRiders",
            "text": "Excellent adversarial demo.",
            "sentences": [],
            "emotion_map": {},
            "generated_at": 1_700_000_000.0,
        }
        (dirs["commentary"] / "riftriders.json").write_text(json.dumps(commentary_data))

        result = await export_team_data("RiftRiders")

        assert result is not None
        assert result.commentary is not None
        assert result.commentary["text"] == "Excellent adversarial demo."

    @pytest.mark.asyncio
    async def test_team_export_commentary_none_when_missing(
        self, tmp_path: Path, monkeypatch
    ):
        """export_team_data leaves commentary as None when no file exists."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="QuietTeam")
        await _write_scorecard(sc, dirs["scores"])

        result = await export_team_data("QuietTeam")

        assert result is not None
        assert result.commentary is None

    @pytest.mark.asyncio
    async def test_team_export_loads_observations(self, tmp_path: Path, monkeypatch):
        """export_team_data includes observations when the file exists."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="Observers")
        await _write_scorecard(sc, dirs["scores"])

        obs_data = {"team_name": "Observers", "observations": ["Watch this"], "transcripts": []}
        (dirs["observations"] / "observers.json").write_text(json.dumps(obs_data))

        result = await export_team_data("Observers")

        assert result is not None
        assert result.observations is not None
        assert result.observations["observations"] == ["Watch this"]

    @pytest.mark.asyncio
    async def test_team_export_loads_human_scores(self, tmp_path: Path, monkeypatch):
        """export_team_data includes human_scores when the file exists."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="JudgedTeam")
        await _write_scorecard(sc, dirs["scores"])

        human_data = [
            {"judge_name": "Carol", "team_name": "JudgedTeam", "total_score": 9.0, "notes": "", "submitted_at": 0.0},
        ]
        (dirs["human_scores"] / "judgedteam.json").write_text(json.dumps(human_data))

        result = await export_team_data("JudgedTeam")

        assert result is not None
        assert len(result.human_scores) == 1
        assert result.human_scores[0]["judge_name"] == "Carol"

    @pytest.mark.asyncio
    async def test_team_export_human_scores_empty_when_missing(
        self, tmp_path: Path, monkeypatch
    ):
        """export_team_data returns empty human_scores when no file exists."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="UnjudgedTeam")
        await _write_scorecard(sc, dirs["scores"])

        result = await export_team_data("UnjudgedTeam")

        assert result is not None
        assert result.human_scores == []

    @pytest.mark.asyncio
    async def test_team_name_with_spaces_resolved_correctly(
        self, tmp_path: Path, monkeypatch
    ):
        """Team names with spaces are correctly sanitized for file lookup."""
        dirs = _redirect_export_dirs(monkeypatch, tmp_path)
        sc = make_scorecard(team_name="Cyber Falcons")
        await _write_scorecard(sc, dirs["scores"])

        # File should be written as cyber_falcons.json by the store
        result = await export_team_data("Cyber Falcons")

        assert result is not None
        assert result.team_name == "Cyber Falcons"
        assert result.ai_score == 7.5


# ---------------------------------------------------------------------------
# Tests: EventLogger.load_tail
# ---------------------------------------------------------------------------


class TestEventLoggerLoadTail:
    """Tests for EventLogger.load_tail — O(1)-memory tail reading."""

    def test_load_tail_returns_last_n(self, tmp_path: Path):
        """load_tail with max_entries=10 returns the last 10 of 50 entries."""
        from src.capture.event_logger import EventLogger

        path = tmp_path / "events.jsonl"
        lines = [json.dumps({"i": i}) for i in range(50)]
        path.write_text("\n".join(lines) + "\n")

        result = EventLogger.load_tail(path, max_entries=10)
        assert len(result) == 10
        assert result[0]["i"] == 40
        assert result[-1]["i"] == 49

    def test_load_tail_missing_file(self, tmp_path: Path):
        """load_tail returns empty list when file does not exist."""
        from src.capture.event_logger import EventLogger

        path = tmp_path / "nope.jsonl"
        result = EventLogger.load_tail(path, max_entries=10)
        assert result == []

    def test_load_tail_all_when_under_cap(self, tmp_path: Path):
        """load_tail returns all entries when count is below max_entries."""
        from src.capture.event_logger import EventLogger

        path = tmp_path / "events.jsonl"
        lines = [json.dumps({"i": i}) for i in range(3)]
        path.write_text("\n".join(lines) + "\n")

        result = EventLogger.load_tail(path, max_entries=100)
        assert len(result) == 3

    def test_load_tail_skips_malformed_lines(self, tmp_path: Path):
        """load_tail skips lines that are not valid JSON."""
        from src.capture.event_logger import EventLogger

        path = tmp_path / "events.jsonl"
        path.write_text('{"i": 0}\nnot json\n{"i": 1}\n')

        result = EventLogger.load_tail(path, max_entries=100)
        assert len(result) == 2
        assert result[0]["i"] == 0
        assert result[1]["i"] == 1


# ---------------------------------------------------------------------------
# Tests: export_event_data — capped log loading (issue #78)
# ---------------------------------------------------------------------------


class TestExportCappedLogs:
    """Tests for capped audit/event log loading (memory-safety fix for issue #78)."""

    @pytest.fixture(autouse=True)
    def setup_dirs(self, tmp_path: Path, monkeypatch):
        """Set up temp directories for test isolation."""
        import src.reports.export as export_mod

        self.scores_dir = tmp_path / "scores"
        self.scores_dir.mkdir()
        self.audit_path = tmp_path / "audit.jsonl"
        self.events_path = tmp_path / "events.jsonl"
        self.obs_dir = tmp_path / "observations"
        self.obs_dir.mkdir()
        self.commentary_dir = tmp_path / "commentary"
        self.commentary_dir.mkdir()
        self.human_dir = tmp_path / "human_scores"
        self.human_dir.mkdir()
        self.delib_dir = tmp_path / "deliberation"
        self.delib_dir.mkdir()

        monkeypatch.setattr(export_mod, "SCORES_DIR", self.scores_dir)
        monkeypatch.setattr(export_mod, "AUDIT_LOG", self.audit_path)
        monkeypatch.setattr(export_mod, "EVENTS_LOG", self.events_path)
        monkeypatch.setattr(export_mod, "OBSERVATIONS_DIR", self.obs_dir)
        monkeypatch.setattr(export_mod, "COMMENTARY_DIR", self.commentary_dir)
        monkeypatch.setattr(export_mod, "HUMAN_SCORES_DIR", self.human_dir)
        monkeypatch.setattr(export_mod, "DELIBERATION_DIR", self.delib_dir)

    @pytest.mark.asyncio
    async def test_audit_log_capped_to_max_entries(self):
        """When audit log has more entries than max, only last N are returned."""
        lines = [json.dumps({"seq": i, "action": "test"}) for i in range(20)]
        self.audit_path.write_text("\n".join(lines) + "\n")

        result = await export_event_data(include_audit=True, max_audit_entries=5)
        assert len(result.audit_log) == 5
        # Should be the LAST 5 entries
        assert result.audit_log[0]["seq"] == 15
        assert result.audit_log[-1]["seq"] == 19

    @pytest.mark.asyncio
    async def test_event_log_capped_to_max_entries(self):
        """When event log has more entries than max, only last N are returned."""
        lines = [json.dumps({"seq": i, "type": "test"}) for i in range(20)]
        self.events_path.write_text("\n".join(lines) + "\n")

        result = await export_event_data(include_events=True, max_event_entries=5)
        assert len(result.event_log) == 5
        assert result.event_log[0]["seq"] == 15

    @pytest.mark.asyncio
    async def test_audit_under_cap_returns_all(self):
        """When audit log has fewer entries than max, all are returned."""
        lines = [json.dumps({"seq": i}) for i in range(3)]
        self.audit_path.write_text("\n".join(lines) + "\n")

        result = await export_event_data(include_audit=True, max_audit_entries=100)
        assert len(result.audit_log) == 3

    @pytest.mark.asyncio
    async def test_malformed_lines_skipped(self):
        """Malformed JSONL lines are skipped without error."""
        self.audit_path.write_text('{"seq": 0}\nnot json\n{"seq": 1}\n')

        result = await export_event_data(include_audit=True, max_audit_entries=100)
        assert len(result.audit_log) == 2

    @pytest.mark.asyncio
    async def test_default_cap_is_ten_thousand(self):
        """Default max_audit_entries=10_000 is accepted without error."""
        lines = [json.dumps({"seq": i}) for i in range(5)]
        self.audit_path.write_text("\n".join(lines) + "\n")

        # No max_audit_entries kwarg — should use the default (10_000) fine
        result = await export_event_data(include_audit=True)
        assert len(result.audit_log) == 5
