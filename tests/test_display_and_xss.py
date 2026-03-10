"""Tests for ConnectionManager state cache, XSS prevention, and critical E2E gaps.

Covers:
- Late-joiner replay ordering and clear semantics
- Criteria sequence accumulation and commentary-clear behavior
- Failed client removal during broadcast
- XSS escaping in report card HTML (team name, justification, commentary)
- CancelledError propagation in score reveal
- Commentary/scorecard team name mismatch handling
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.event_bus import EventBus
from src.commentary.display_server import ConnectionManager, DisplayServer
from src.commentary.models import CommentaryDelivered
from src.reports.card import _render_html
from src.scoring.models import CriterionScore, DemoScorecard
from src.scoring.pipeline import ScoringPipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_ws() -> AsyncMock:
    """Create a mock WebSocket with send_json and accept methods."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    ws.accept = AsyncMock()
    return ws


def _make_scorecard(
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
        ],
        track_bonus=None,
        total_score=total_score,
        scored_at=scored_at,
    )


# ---------------------------------------------------------------------------
# ConnectionManager state cache tests
# ---------------------------------------------------------------------------


class TestConnectionManagerStateCache:
    """Tests for late-joiner replay and screen state tracking."""

    @pytest.mark.asyncio
    async def test_late_joiner_receives_full_score_sequence_in_order(self):
        """After score_intro, two score_criterion, and score_total broadcasts,
        a newly connected client receives all four messages in order."""
        mgr = ConnectionManager()

        intro = {"type": "score_intro", "team_name": "AlphaTeam"}
        crit0 = {"type": "score_criterion", "name": "C0", "score": 8.0, "weight": 0.4, "justification": "Good"}
        crit1 = {"type": "score_criterion", "name": "C1", "score": 7.0, "weight": 0.3, "justification": "Nice"}
        total = {"type": "score_total", "team_name": "AlphaTeam", "total_score": 7.5, "track": "ROGUE::AGENT"}

        await mgr.broadcast(intro)
        await mgr.broadcast(crit0)
        await mgr.broadcast(crit1)
        await mgr.broadcast(total)

        # Connect a late-joiner mock WebSocket
        late_ws = _make_mock_ws()
        await mgr.connect(late_ws)

        # Verify send_json calls: intro, crit0, crit1, total
        calls = late_ws.send_json.call_args_list
        assert len(calls) == 4
        assert calls[0].args[0] == intro
        assert calls[1].args[0] == crit0
        assert calls[2].args[0] == crit1
        assert calls[3].args[0] == total

    @pytest.mark.asyncio
    async def test_late_joiner_after_clear_receives_no_replay(self):
        """After building score cache then broadcasting clear,
        a newly connected client receives no replayed messages."""
        mgr = ConnectionManager()

        await mgr.broadcast({"type": "score_intro", "team_name": "TeamX"})
        await mgr.broadcast({"type": "score_criterion", "name": "C0", "score": 5.0, "weight": 0.5, "justification": "OK"})
        await mgr.broadcast({"type": "score_total", "team_name": "TeamX", "total_score": 5.0, "track": "ROGUE::AGENT"})
        await mgr.broadcast({"type": "clear"})

        late_ws = _make_mock_ws()
        await mgr.connect(late_ws)

        # Only accept was called, no send_json replay
        late_ws.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_score_criterion_accumulates_without_replacing_last_screen_state(self):
        """score_criterion messages accumulate in _criteria_sequence without
        overwriting _last_screen_state, which stays as score_intro."""
        mgr = ConnectionManager()

        intro = {"type": "score_intro", "team_name": "TeamY"}
        await mgr.broadcast(intro)

        for i in range(3):
            await mgr.broadcast({
                "type": "score_criterion",
                "name": f"C{i}",
                "score": 6.0 + i,
                "weight": 0.33,
                "justification": f"Reason {i}",
            })

        assert mgr._last_screen_state == intro
        assert len(mgr._criteria_sequence) == 3

    @pytest.mark.asyncio
    async def test_commentary_broadcast_clears_criteria_sequence(self):
        """Broadcasting a commentary message clears _criteria_sequence."""
        mgr = ConnectionManager()

        await mgr.broadcast({"type": "score_intro", "team_name": "TeamZ"})
        await mgr.broadcast({"type": "score_criterion", "name": "C0", "score": 7.0, "weight": 0.5, "justification": "OK"})
        await mgr.broadcast({"type": "score_criterion", "name": "C1", "score": 8.0, "weight": 0.5, "justification": "Good"})

        assert len(mgr._criteria_sequence) == 2

        await mgr.broadcast({"type": "commentary", "text": "Great job!", "team_name": "TeamZ"})

        assert mgr._criteria_sequence == []
        assert mgr._last_screen_state["type"] == "commentary"


class TestBroadcastClientFailure:
    """Tests for failed client removal during broadcast."""

    @pytest.mark.asyncio
    async def test_broadcast_removes_failed_client_delivers_to_healthy(self):
        """When one client raises on send_json, it is removed from active
        connections and the healthy client still receives the message."""
        mgr = ConnectionManager()

        bad_ws = _make_mock_ws()
        bad_ws.send_json.side_effect = RuntimeError("Connection closed")

        good_ws = _make_mock_ws()

        # Manually add to active (bypass accept handshake)
        mgr.active.append(bad_ws)
        mgr.active.append(good_ws)

        msg = {"type": "commentary", "text": "Hello!", "team_name": "TeamA"}
        await mgr.broadcast(msg)

        # Bad client removed, good client remains
        assert bad_ws not in mgr.active
        assert good_ws in mgr.active
        good_ws.send_json.assert_called_once_with(msg)


# ---------------------------------------------------------------------------
# XSS prevention tests
# ---------------------------------------------------------------------------


class TestXSSPrevention:
    """Tests that _render_html escapes user-controlled content."""

    def test_xss_escaped_in_team_name(self):
        """Script tags in team_name are HTML-escaped."""
        sc = _make_scorecard(team_name="<script>alert(1)</script>")
        html = _render_html(sc, "")
        assert "&lt;script&gt;" in html
        assert "<script>alert(1)</script>" not in html

    def test_xss_escaped_in_criterion_justification(self):
        """Image onerror XSS in justification is HTML-escaped."""
        sc = _make_scorecard()
        sc.criteria[0].justification = '<img src=x onerror=alert(1)>'
        html = _render_html(sc, "")
        assert "&lt;img src=x onerror=alert(1)&gt;" in html
        assert '<img src=x onerror=alert(1)>' not in html

    def test_xss_escaped_in_commentary(self):
        """Script tags in commentary text are HTML-escaped."""
        sc = _make_scorecard()
        commentary = '<script>document.cookie</script>'
        html = _render_html(sc, commentary)
        assert "&lt;script&gt;" in html
        assert "<script>document.cookie</script>" not in html


# ---------------------------------------------------------------------------
# CancelledError propagation in score reveal
# ---------------------------------------------------------------------------


class TestRevealScoreCancellation:
    """Tests that _reveal_score properly re-raises CancelledError."""

    @pytest.mark.asyncio
    async def test_reveal_score_cancelled_error_propagates(self):
        """Cancelling the reveal task mid-execution raises CancelledError."""
        display = MagicMock(spec=DisplayServer)

        # Make push_score_intro do a long sleep so we can cancel mid-reveal
        async def slow_intro(*args, **kwargs):
            await asyncio.sleep(10.0)

        display.push_score_intro = AsyncMock(side_effect=slow_intro)
        display.push_criterion_reveal = AsyncMock()
        display.push_total_score = AsyncMock()

        pipeline = ScoringPipeline.__new__(ScoringPipeline)
        pipeline._display = display
        pipeline._event_bus = None
        pipeline._reveal_task = None

        scorecard = _make_scorecard()

        task = asyncio.create_task(pipeline._reveal_score(scorecard))
        # Let the task start executing
        await asyncio.sleep(0.01)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task


# ---------------------------------------------------------------------------
# Commentary / scorecard team name mismatch
# ---------------------------------------------------------------------------


class TestCommentaryTeamMismatch:
    """Tests that a team name mismatch between commentary and scorecard
    does not trigger a score reveal for the wrong team."""

    @pytest.mark.asyncio
    async def test_commentary_team_name_mismatch_drops_scorecard(self):
        """CommentaryDelivered for 'TeamX' when scorecard stored for 'TeamY'
        does not trigger a reveal and TeamY scorecard remains pending."""
        display = MagicMock(spec=DisplayServer)
        display.push_score_intro = AsyncMock()
        display.push_criterion_reveal = AsyncMock()
        display.push_total_score = AsyncMock()

        pipeline = ScoringPipeline.__new__(ScoringPipeline)
        pipeline._display = display
        pipeline._event_bus = EventBus()
        pipeline._reveal_task = None
        pipeline._pending_scorecards = {}

        # Store scorecard for TeamY
        scorecard_y = _make_scorecard(team_name="TeamY")
        pipeline._pending_scorecards["TeamY"] = scorecard_y

        # Deliver commentary for TeamX (mismatch)
        event = CommentaryDelivered(team_name="TeamX", commentary_text="Nice work TeamX")
        await pipeline._on_commentary_delivered(event)

        # No reveal should have been launched
        assert pipeline._reveal_task is None
        display.push_score_intro.assert_not_called()

        # TeamY scorecard is still pending
        assert "TeamY" in pipeline._pending_scorecards
        assert pipeline._pending_scorecards["TeamY"] is scorecard_y
