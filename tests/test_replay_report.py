"""Tests for the replay report generator (pure functions)."""

from __future__ import annotations

from src.memory.models import DeliberationResult, TeamRanking
from src.replay.report import _build_json, _build_markdown
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
        rank_lines = [l for l in lines if l.startswith("| ") and "Rank" not in l and "---" not in l]
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
