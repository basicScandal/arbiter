"""Test suite for the per-team report card HTML generator.

Tests generate_report_card_html for missing teams, valid scorecards,
HTML structure, print button presence, and all tier label thresholds.
Uses temporary directories with real JSON scorecard data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.reports.card import _render_html, generate_report_card_html
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
    with_bonus: bool = False,
) -> DemoScorecard:
    """Build a minimal DemoScorecard for testing."""
    criteria = [
        CriterionScore(
            name="Technical Execution",
            score=8.0,
            weight=0.40,
            justification="Solid implementation.",
        ),
        CriterionScore(
            name="Innovation",
            score=7.0,
            weight=0.30,
            justification="Novel approach.",
        ),
        CriterionScore(
            name="Demo Quality",
            score=7.0,
            weight=0.30,
            justification="Clear presentation.",
        ),
    ]
    track_bonus = None
    if with_bonus:
        track_bonus = CriterionScore(
            name="Attack Effectiveness",
            score=8.5,
            weight=0.15,
            justification="Demonstrated effective attack vector.",
        )
    return DemoScorecard(
        team_name=team_name,
        track=track,
        criteria=criteria,
        track_bonus=track_bonus,
        total_score=total_score,
        scored_at=scored_at,
    )


async def _write_scorecard(scorecard: DemoScorecard, scores_dir: Path) -> None:
    """Write a scorecard JSON file into scores_dir using the store's naming convention."""
    from src.scoring.store import ScoreStore

    store = ScoreStore(scores_dir=str(scores_dir))
    await store.save(scorecard)


# ---------------------------------------------------------------------------
# Tests: generate_report_card_html (async, uses file I/O)
# ---------------------------------------------------------------------------


class TestGenerateReportCardHtml:
    """Tests for generate_report_card_html."""

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_team(self, tmp_path: Path, monkeypatch):
        """Returns None when no scorecard file exists for the team."""
        monkeypatch.setattr("src.reports.card.SCORES_DIR", tmp_path / "scores")
        result = await generate_report_card_html("NoSuchTeam")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_html_for_existing_team(self, tmp_path: Path, monkeypatch):
        """Returns an HTML string when a valid scorecard exists."""
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir()
        monkeypatch.setattr("src.reports.card.SCORES_DIR", scores_dir)
        monkeypatch.setattr("src.reports.card.COMMENTARY_DIR", tmp_path / "commentary")

        scorecard = make_scorecard()
        await _write_scorecard(scorecard, scores_dir)

        html = await generate_report_card_html("CyberFalcons")
        assert html is not None
        assert isinstance(html, str)
        assert len(html) > 100

    @pytest.mark.asyncio
    async def test_html_contains_team_name(self, tmp_path: Path, monkeypatch):
        """Generated HTML contains the team name."""
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir()
        monkeypatch.setattr("src.reports.card.SCORES_DIR", scores_dir)
        monkeypatch.setattr("src.reports.card.COMMENTARY_DIR", tmp_path / "commentary")

        scorecard = make_scorecard(team_name="NightOwls")
        await _write_scorecard(scorecard, scores_dir)

        html = await generate_report_card_html("NightOwls")
        assert html is not None
        assert "NightOwls" in html

    @pytest.mark.asyncio
    async def test_html_contains_total_score(self, tmp_path: Path, monkeypatch):
        """Generated HTML contains the total score."""
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir()
        monkeypatch.setattr("src.reports.card.SCORES_DIR", scores_dir)
        monkeypatch.setattr("src.reports.card.COMMENTARY_DIR", tmp_path / "commentary")

        scorecard = make_scorecard(total_score=8.3)
        await _write_scorecard(scorecard, scores_dir)

        html = await generate_report_card_html("CyberFalcons")
        assert html is not None
        assert "8.3" in html

    @pytest.mark.asyncio
    async def test_html_contains_criteria_names(self, tmp_path: Path, monkeypatch):
        """Generated HTML contains each criterion name."""
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir()
        monkeypatch.setattr("src.reports.card.SCORES_DIR", scores_dir)
        monkeypatch.setattr("src.reports.card.COMMENTARY_DIR", tmp_path / "commentary")

        scorecard = make_scorecard()
        await _write_scorecard(scorecard, scores_dir)

        html = await generate_report_card_html("CyberFalcons")
        assert html is not None
        assert "Technical Execution" in html
        assert "Innovation" in html
        assert "Demo Quality" in html

    @pytest.mark.asyncio
    async def test_html_contains_print_button(self, tmp_path: Path, monkeypatch):
        """Generated HTML includes the SAVE AS PDF print button."""
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir()
        monkeypatch.setattr("src.reports.card.SCORES_DIR", scores_dir)
        monkeypatch.setattr("src.reports.card.COMMENTARY_DIR", tmp_path / "commentary")

        scorecard = make_scorecard()
        await _write_scorecard(scorecard, scores_dir)

        html = await generate_report_card_html("CyberFalcons")
        assert html is not None
        assert "window.print()" in html
        assert "SAVE AS PDF" in html

    @pytest.mark.asyncio
    async def test_html_with_commentary(self, tmp_path: Path, monkeypatch):
        """Commentary text is embedded in the HTML when a commentary file exists."""
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir()
        commentary_dir = tmp_path / "commentary"
        commentary_dir.mkdir()
        monkeypatch.setattr("src.reports.card.SCORES_DIR", scores_dir)
        monkeypatch.setattr("src.reports.card.COMMENTARY_DIR", commentary_dir)

        scorecard = make_scorecard(team_name="AlphaTeam")
        await _write_scorecard(scorecard, scores_dir)

        # Write a commentary file using the sanitized team name
        commentary_data = {
            "team_name": "AlphaTeam",
            "text": "An outstanding demonstration of adversarial techniques.",
            "sentences": ["An outstanding demonstration of adversarial techniques."],
            "emotion_map": {},
            "generated_at": 1_700_000_000.0,
        }
        (commentary_dir / "alphateam.json").write_text(json.dumps(commentary_data))

        html = await generate_report_card_html("AlphaTeam")
        assert html is not None
        assert "An outstanding demonstration of adversarial techniques." in html
        assert "ARBITER'S COMMENTARY" in html

    @pytest.mark.asyncio
    async def test_html_without_commentary_still_valid(self, tmp_path: Path, monkeypatch):
        """HTML is generated correctly even without a commentary file."""
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir()
        monkeypatch.setattr("src.reports.card.SCORES_DIR", scores_dir)
        monkeypatch.setattr("src.reports.card.COMMENTARY_DIR", tmp_path / "no_commentary")

        scorecard = make_scorecard()
        await _write_scorecard(scorecard, scores_dir)

        html = await generate_report_card_html("CyberFalcons")
        assert html is not None
        assert "<!DOCTYPE html>" in html
        assert "ARBITER'S COMMENTARY" not in html

    @pytest.mark.asyncio
    async def test_html_with_track_bonus(self, tmp_path: Path, monkeypatch):
        """Track bonus criterion is rendered in the HTML when present."""
        scores_dir = tmp_path / "scores"
        scores_dir.mkdir()
        monkeypatch.setattr("src.reports.card.SCORES_DIR", scores_dir)
        monkeypatch.setattr("src.reports.card.COMMENTARY_DIR", tmp_path / "commentary")

        scorecard = make_scorecard(with_bonus=True)
        await _write_scorecard(scorecard, scores_dir)

        html = await generate_report_card_html("CyberFalcons")
        assert html is not None
        assert "Attack Effectiveness" in html
        assert "bonus-bar" in html


# ---------------------------------------------------------------------------
# Tests: _render_html tier labels
# ---------------------------------------------------------------------------


class TestTierLabels:
    """Tests for score tier label assignment in _render_html."""

    def test_tier_exceptional_at_9(self):
        """Score of 9.0 yields EXCEPTIONAL tier."""
        sc = make_scorecard(total_score=9.0)
        html = _render_html(sc, "")
        assert "EXCEPTIONAL" in html
        assert "tier-exceptional" in html

    def test_tier_exceptional_at_10(self):
        """Score of 10.0 yields EXCEPTIONAL tier."""
        sc = make_scorecard(total_score=10.0)
        html = _render_html(sc, "")
        assert "EXCEPTIONAL" in html

    def test_tier_strong_at_7(self):
        """Score of 7.0 yields STRONG tier."""
        sc = make_scorecard(total_score=7.0)
        html = _render_html(sc, "")
        assert "STRONG" in html
        assert "tier-strong" in html

    def test_tier_strong_at_8_5(self):
        """Score of 8.5 (below 9) yields STRONG tier."""
        sc = make_scorecard(total_score=8.5)
        html = _render_html(sc, "")
        assert "STRONG" in html

    def test_tier_solid_at_5(self):
        """Score of 5.0 yields SOLID tier."""
        sc = make_scorecard(total_score=5.0)
        html = _render_html(sc, "")
        assert "SOLID" in html
        assert "tier-solid" in html

    def test_tier_solid_at_6_9(self):
        """Score of 6.9 (below 7) yields SOLID tier."""
        sc = make_scorecard(total_score=6.9)
        html = _render_html(sc, "")
        assert "SOLID" in html

    def test_tier_developing_at_4_9(self):
        """Score of 4.9 (below 5) yields DEVELOPING tier."""
        sc = make_scorecard(total_score=4.9)
        html = _render_html(sc, "")
        assert "DEVELOPING" in html
        assert "tier-developing" in html

    def test_tier_developing_at_0(self):
        """Score of 0.0 yields DEVELOPING tier."""
        sc = make_scorecard(total_score=0.0)
        html = _render_html(sc, "")
        assert "DEVELOPING" in html


# ---------------------------------------------------------------------------
# Tests: _render_html HTML structure
# ---------------------------------------------------------------------------


class TestRenderHtmlStructure:
    """Tests for general HTML structure produced by _render_html."""

    def test_is_valid_html_document(self):
        """Output starts with a DOCTYPE and ends with closing html tag."""
        sc = make_scorecard()
        html = _render_html(sc, "")
        assert html.strip().startswith("<!DOCTYPE html>")
        assert html.strip().endswith("</html>")

    def test_contains_title_with_team_name(self):
        """<title> element includes the team name."""
        sc = make_scorecard(team_name="PixelCrew")
        html = _render_html(sc, "")
        assert "<title>Report Card — PixelCrew</title>" in html

    def test_contains_track_badge(self):
        """Track name appears in the rendered HTML."""
        sc = make_scorecard(track="SHADOW::VECTOR")
        html = _render_html(sc, "")
        assert "SHADOW::VECTOR" in html

    def test_contains_print_media_query(self):
        """CSS contains a print media query for PDF output."""
        sc = make_scorecard()
        html = _render_html(sc, "")
        assert "@media print" in html

    def test_no_track_bonus_section_when_absent(self):
        """When track_bonus is None, no bonus criterion name is rendered."""
        sc = make_scorecard(with_bonus=False)
        html = _render_html(sc, "")
        # "bonus-row" class only appears in the <tr> element emitted for the bonus row,
        # not in the CSS (which uses ".bonus-bar" and ".score-value.bonus").
        assert 'class="bonus-row"' not in html

    def test_track_bonus_section_present_when_set(self):
        """When track_bonus is set, its name and bonus-row class appear in HTML."""
        sc = make_scorecard(with_bonus=True)
        html = _render_html(sc, "")
        assert "Attack Effectiveness" in html
        assert 'class="bonus-row"' in html

    def test_footer_contains_arbiter_branding(self):
        """Footer mentions ARBITER brand text."""
        sc = make_scorecard()
        html = _render_html(sc, "")
        assert "ARBITER" in html
        assert "Autonomous AI Judge System" in html

    def test_commentary_blockquote_rendered(self):
        """Commentary text is wrapped in a blockquote element."""
        sc = make_scorecard()
        commentary = "This team showed exceptional creativity."
        html = _render_html(sc, commentary)
        assert '<blockquote class="commentary">' in html
        assert "This team showed exceptional creativity." in html

    def test_no_commentary_blockquote_when_empty(self):
        """No blockquote element is rendered when commentary is empty."""
        sc = make_scorecard()
        html = _render_html(sc, "")
        assert "blockquote" not in html

    def test_score_bars_have_correct_width(self):
        """Score bar widths are computed as score * 10 percent."""
        sc = make_scorecard()
        html = _render_html(sc, "")
        # Technical Execution score=8.0 -> width: 80.0%
        assert "width: 80.0%" in html
        # Innovation score=7.0 -> width: 70.0%
        assert "width: 70.0%" in html
