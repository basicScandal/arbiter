"""Tests for the replay report generator (pure functions and async I/O)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.memory.models import DeliberationResult, TeamRanking
from src.replay.report import (
    _build_json,
    _build_markdown,
    _load_deliberation,
    _load_scorecards,
    generate_report,
)
from src.scoring.models import CriterionScore, DemoScorecard

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_scorecard(
    team: str = "TeamA",
    track: str = "ROGUE::AGENT",
    score: float = 7.5,
) -> DemoScorecard:
    return DemoScorecard(
        team_name=team,
        track=track,
        criteria=[
            CriterionScore(name="Technical", score=8.0, weight=0.4, justification="Solid work"),
            CriterionScore(name="Innovation", score=7.0, weight=0.3, justification="Novel approach"),
        ],
        track_bonus=CriterionScore(
            name="Bonus", score=6.0, weight=0.1, justification="Good effort",
        ),
        total_score=score,
        scored_at=1700000000.0,
    )


def _make_deliberation() -> DeliberationResult:
    return DeliberationResult(
        rankings=[
            TeamRanking(
                rank=1,
                team_name="TeamA",
                track="ROGUE::AGENT",
                total_score=7.5,
                strengths=["Clean code", "Fast demo"],
                weaknesses=["Rushed Q&A"],
                cross_references=["Better than TeamB on execution"],
                reasoning="Strong overall performance",
            ),
        ],
        overall_narrative="An impressive showing overall.",
        notable_themes=["AI-driven security", "Graph analysis"],
        deliberated_at=1700000100.0,
    )


# ---------------------------------------------------------------------------
# _build_markdown
# ---------------------------------------------------------------------------


class TestBuildMarkdown:
    def test_header_present(self):
        md = _build_markdown([], None)
        assert "# NEBULA:FOG:PRIME Replay Report" in md

    def test_demo_count(self):
        cards = [_make_scorecard("A", score=8.0), _make_scorecard("B", score=6.0)]
        md = _build_markdown(cards, None)
        assert "Total demos scored: 2" in md

    def test_scoreboard_sorted_descending(self):
        cards = [
            _make_scorecard("Low", score=3.0),
            _make_scorecard("High", score=9.0),
            _make_scorecard("Mid", score=6.0),
        ]
        md = _build_markdown(cards, None)
        lines = md.split("\n")
        # Find the rank rows
        rank_lines = [ln for ln in lines if ln.startswith("| ") and "Rank" not in ln and "---" not in ln]
        assert "High" in rank_lines[0]
        assert "Mid" in rank_lines[1]
        assert "Low" in rank_lines[2]

    def test_criteria_details(self):
        card = _make_scorecard()
        md = _build_markdown([card], None)
        assert "**Technical**" in md
        assert "Solid work" in md
        assert "**Innovation**" in md
        assert "**Bonus**" in md

    def test_deliberation_section(self):
        delib = _make_deliberation()
        md = _build_markdown([], delib)
        assert "## Deliberation" in md
        assert "An impressive showing overall." in md
        assert "AI-driven security" in md
        assert "Graph analysis" in md
        assert "Strong overall performance" in md
        assert "Clean code" in md
        assert "Rushed Q&A" in md

    def test_no_deliberation_omits_section(self):
        md = _build_markdown([], None)
        assert "## Deliberation" not in md

    def test_no_scorecards_omits_scoreboard(self):
        md = _build_markdown([], None)
        assert "## Scoreboard" not in md


# ---------------------------------------------------------------------------
# _build_json
# ---------------------------------------------------------------------------


class TestBuildJson:
    def test_structure(self):
        result = _build_json([], None)
        assert "generated_at" in result
        assert result["total_demos"] == 0
        assert result["scorecards"] == []
        assert result["deliberation"] is None

    def test_scorecards_sorted(self):
        cards = [
            _make_scorecard("Low", score=2.0),
            _make_scorecard("High", score=9.0),
        ]
        result = _build_json(cards, None)
        assert result["total_demos"] == 2
        assert result["scorecards"][0]["team_name"] == "High"
        assert result["scorecards"][1]["team_name"] == "Low"

    def test_deliberation_included(self):
        delib = _make_deliberation()
        result = _build_json([], delib)
        assert result["deliberation"] is not None
        assert result["deliberation"]["overall_narrative"] == "An impressive showing overall."


# ---------------------------------------------------------------------------
# _load_scorecards
# ---------------------------------------------------------------------------


class TestLoadScorecards:
    @pytest.mark.asyncio
    async def test_returns_empty_when_dir_missing(self, tmp_path: Path):
        nonexistent = tmp_path / "no_such_dir"
        with patch("src.replay.report.SCORES_DIR", nonexistent):
            result = await _load_scorecards()
        assert result == []

    @pytest.mark.asyncio
    async def test_loads_valid_scorecard(self, tmp_path: Path):
        card = _make_scorecard("AlphaTeam", score=8.5)
        (tmp_path / "001.json").write_text(card.model_dump_json())

        with patch("src.replay.report.SCORES_DIR", tmp_path):
            result = await _load_scorecards()

        assert len(result) == 1
        assert result[0].team_name == "AlphaTeam"
        assert result[0].total_score == 8.5

    @pytest.mark.asyncio
    async def test_loads_multiple_scorecards(self, tmp_path: Path):
        for i, name in enumerate(["A", "B", "C"], 1):
            card = _make_scorecard(name, score=float(i))
            (tmp_path / f"{i:03}.json").write_text(card.model_dump_json())

        with patch("src.replay.report.SCORES_DIR", tmp_path):
            result = await _load_scorecards()

        assert len(result) == 3
        names = {c.team_name for c in result}
        assert names == {"A", "B", "C"}

    @pytest.mark.asyncio
    async def test_skips_invalid_json(self, tmp_path: Path):
        (tmp_path / "good.json").write_text(_make_scorecard("Good").model_dump_json())
        (tmp_path / "bad.json").write_text("not valid json {{{{")

        with patch("src.replay.report.SCORES_DIR", tmp_path):
            result = await _load_scorecards()

        assert len(result) == 1
        assert result[0].team_name == "Good"

    @pytest.mark.asyncio
    async def test_only_loads_json_files(self, tmp_path: Path):
        (tmp_path / "card.json").write_text(_make_scorecard("Valid").model_dump_json())
        (tmp_path / "notes.txt").write_text("ignored")
        (tmp_path / "card.csv").write_text("ignored")

        with patch("src.replay.report.SCORES_DIR", tmp_path):
            result = await _load_scorecards()

        assert len(result) == 1


# ---------------------------------------------------------------------------
# _load_deliberation
# ---------------------------------------------------------------------------


class TestLoadDeliberation:
    @pytest.mark.asyncio
    async def test_returns_none_when_dir_missing(self, tmp_path: Path):
        nonexistent = tmp_path / "no_such_dir"
        with patch("src.replay.report.DELIBERATION_DIR", nonexistent):
            result = await _load_deliberation()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_file_missing(self, tmp_path: Path):
        with patch("src.replay.report.DELIBERATION_DIR", tmp_path):
            result = await _load_deliberation()
        assert result is None

    @pytest.mark.asyncio
    async def test_loads_valid_deliberation(self, tmp_path: Path):
        delib = _make_deliberation()
        (tmp_path / "result.json").write_text(delib.model_dump_json())

        with patch("src.replay.report.DELIBERATION_DIR", tmp_path):
            result = await _load_deliberation()

        assert result is not None
        assert result.overall_narrative == "An impressive showing overall."
        assert result.notable_themes == ["AI-driven security", "Graph analysis"]

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_json(self, tmp_path: Path):
        (tmp_path / "result.json").write_text("not json {{")

        with patch("src.replay.report.DELIBERATION_DIR", tmp_path):
            result = await _load_deliberation()

        assert result is None


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    @pytest.mark.asyncio
    async def test_writes_report_md_and_json(self, tmp_path: Path):
        card = _make_scorecard("TeamX", score=7.0)
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir()
        (scores_dir / "001.json").write_text(card.model_dump_json())

        delib = _make_deliberation()
        delib_dir = tmp_path / "deliberation"
        delib_dir.mkdir()
        (delib_dir / "result.json").write_text(delib.model_dump_json())

        with (
            patch("src.replay.report.SCORES_DIR", scores_dir),
            patch("src.replay.report.DELIBERATION_DIR", delib_dir),
            patch("src.replay.report.BASE_DIR", tmp_path),
        ):
            await generate_report()

        assert (tmp_path / "report.md").exists()
        assert (tmp_path / "report.json").exists()

    @pytest.mark.asyncio
    async def test_report_md_contains_team_name(self, tmp_path: Path):
        card = _make_scorecard("UniqueTeamName", score=9.0)
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir()
        (scores_dir / "001.json").write_text(card.model_dump_json())

        delib_dir = tmp_path / "deliberation"
        delib_dir.mkdir()

        with (
            patch("src.replay.report.SCORES_DIR", scores_dir),
            patch("src.replay.report.DELIBERATION_DIR", delib_dir),
            patch("src.replay.report.BASE_DIR", tmp_path),
        ):
            await generate_report()

        md_content = (tmp_path / "report.md").read_text()
        assert "UniqueTeamName" in md_content

    @pytest.mark.asyncio
    async def test_report_json_is_valid(self, tmp_path: Path):
        card = _make_scorecard("JsonTeam", score=6.5)
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir()
        (scores_dir / "001.json").write_text(card.model_dump_json())

        delib_dir = tmp_path / "deliberation"
        delib_dir.mkdir()

        with (
            patch("src.replay.report.SCORES_DIR", scores_dir),
            patch("src.replay.report.DELIBERATION_DIR", delib_dir),
            patch("src.replay.report.BASE_DIR", tmp_path),
        ):
            await generate_report()

        raw = (tmp_path / "report.json").read_text()
        parsed = json.loads(raw)
        assert parsed["total_demos"] == 1
        assert parsed["scorecards"][0]["team_name"] == "JsonTeam"
        assert "generated_at" in parsed

    @pytest.mark.asyncio
    async def test_report_with_no_data(self, tmp_path: Path):
        """generate_report works even when scores and deliberation dirs are empty."""
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir()
        delib_dir = tmp_path / "deliberation"
        delib_dir.mkdir()

        with (
            patch("src.replay.report.SCORES_DIR", scores_dir),
            patch("src.replay.report.DELIBERATION_DIR", delib_dir),
            patch("src.replay.report.BASE_DIR", tmp_path),
        ):
            await generate_report()

        parsed = json.loads((tmp_path / "report.json").read_text())
        assert parsed["total_demos"] == 0
        assert parsed["deliberation"] is None
