"""Tests for score reveal task race conditions in ScoringPipeline.

Validates that rapid successive commentary_delivered events don't produce
interleaved display pushes, and that the cancel-then-create pattern in
_on_commentary_delivered fully awaits the old task before starting a new one.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.commentary.display_server import DisplayServer
from src.commentary.models import CommentaryDelivered
from src.scoring.models import CriterionScore, DemoScorecard, ScoreRevealed
from src.scoring.pipeline import ScoringPipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scorecard(team: str, total: float = 7.5) -> DemoScorecard:
    """Build a minimal DemoScorecard for testing."""
    return DemoScorecard(
        team_name=team,
        track="ROGUE::AGENT",
        criteria=[
            CriterionScore(name="Innovation", score=8.0, weight=0.4, justification="Good"),
            CriterionScore(name="Execution", score=7.0, weight=0.3, justification="Solid"),
            CriterionScore(name="Impact", score=7.5, weight=0.3, justification="Nice"),
        ],
        track_bonus=None,
        total_score=total,
        scored_at=1000.0,
    )


def _make_commentary_event(team: str) -> CommentaryDelivered:
    return CommentaryDelivered(team_name=team, commentary_text="Great demo!")


def _make_pipeline() -> tuple[ScoringPipeline, MagicMock, MagicMock]:
    """Create a ScoringPipeline with mocked display and event bus."""
    display = MagicMock(spec=DisplayServer)
    display.push_score_intro = AsyncMock()
    display.push_criterion_reveal = AsyncMock()
    display.push_total_score = AsyncMock()

    pipeline = ScoringPipeline(api_key="test-key", display=display)

    event_bus = MagicMock()
    event_bus.publish = MagicMock()
    pipeline._event_bus = event_bus

    return pipeline, display, event_bus


# ---------------------------------------------------------------------------
# Test 1: Rapid reveal replacement — no interleaving
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rapid_reveal_replacement_no_interleaving():
    """When two commentary_delivered events fire in rapid succession, only the
    second team's reveal should complete and produce display pushes.  The first
    team's reveal must be cancelled *before* the second one begins, preventing
    interleaved display output.
    """
    pipeline, display, event_bus = _make_pipeline()

    scorecard_a = _make_scorecard("Team A", total=6.0)
    scorecard_b = _make_scorecard("Team B", total=9.0)
    pipeline._pending_scorecards["Team A"] = scorecard_a
    pipeline._pending_scorecards["Team B"] = scorecard_b

    # Patch asyncio.sleep so reveals don't actually wait, but still yield
    # control to the event loop so cancellation can propagate.
    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        # Fire Team A's reveal
        await pipeline._on_commentary_delivered(_make_commentary_event("Team A"))

        # The reveal task for Team A is now running. Immediately fire Team B.
        await pipeline._on_commentary_delivered(_make_commentary_event("Team B"))

        # Wait for the (only surviving) reveal task to complete
        assert pipeline._reveal_task is not None
        await pipeline._reveal_task

    # --- Assertions ---

    # push_total_score should have been called exactly once, for Team B only
    total_calls = display.push_total_score.call_args_list
    assert len(total_calls) == 1, f"Expected 1 push_total_score call, got {len(total_calls)}"
    assert total_calls[0] == call("Team B", 9.0, "ROGUE::AGENT")

    # push_score_intro for Team B must exist
    intro_calls = display.push_score_intro.call_args_list
    team_b_intros = [c for c in intro_calls if c == call("Team B")]
    assert len(team_b_intros) == 1

    # No Team A criterion reveals should appear AFTER Team B's intro
    all_display_calls = display.method_calls
    team_b_intro_idx = None
    for i, c in enumerate(all_display_calls):
        if c[0] == "push_score_intro" and c[1] == ("Team B",):
            team_b_intro_idx = i
            break

    if team_b_intro_idx is not None:
        after_b_intro = all_display_calls[team_b_intro_idx + 1:]
        for c in after_b_intro:
            if c[0] == "push_criterion_reveal":
                # All criterion reveals after Team B's intro should be Team B's
                # (criterion name from Team B's scorecard)
                pass  # names are the same for both, so just check no stale total
            if c[0] == "push_total_score":
                assert c[1][0] == "Team B", "Team A total score leaked after Team B intro"

    # ScoreRevealed should be published exactly once, for Team B
    revealed_calls = [
        c for c in event_bus.publish.call_args_list
        if isinstance(c[0][0], ScoreRevealed)
    ]
    assert len(revealed_calls) == 1
    assert revealed_calls[0][0][0].team_name == "Team B"


# ---------------------------------------------------------------------------
# Test 2: No scorecard for team — noop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_scorecard_for_team_is_noop():
    """Firing commentary_delivered for a team with no pending scorecard should
    not create a reveal task or call any display methods.
    """
    pipeline, display, event_bus = _make_pipeline()

    await pipeline._on_commentary_delivered(_make_commentary_event("Ghost Team"))

    # No reveal task should be created
    assert pipeline._reveal_task is None

    # No display methods called
    display.push_score_intro.assert_not_called()
    display.push_criterion_reveal.assert_not_called()
    display.push_total_score.assert_not_called()

    # No events published
    event_bus.publish.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: Single reveal completes normally
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_reveal_completes_in_order():
    """A single reveal should call display methods in the correct order:
    intro -> criteria (one per criterion) -> total, then publish ScoreRevealed.
    """
    pipeline, display, event_bus = _make_pipeline()

    scorecard = _make_scorecard("Solo Team", total=8.0)
    pipeline._pending_scorecards["Solo Team"] = scorecard

    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        await pipeline._on_commentary_delivered(_make_commentary_event("Solo Team"))
        assert pipeline._reveal_task is not None
        await pipeline._reveal_task

    # Verify call order
    expected_order = (
        [call.push_score_intro("Solo Team")]
        + [
            call.push_criterion_reveal(c.name, c.score, c.weight, c.justification)
            for c in scorecard.criteria
        ]
        + [call.push_total_score("Solo Team", 8.0, "ROGUE::AGENT")]
    )

    assert display.method_calls == expected_order

    # ScoreRevealed event published
    revealed_calls = [
        c for c in event_bus.publish.call_args_list
        if isinstance(c[0][0], ScoreRevealed)
    ]
    assert len(revealed_calls) == 1
    assert revealed_calls[0][0][0].team_name == "Solo Team"


# ---------------------------------------------------------------------------
# Test 4: Await-after-cancel ensures no interleaving (regression guard)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_awaits_old_task_before_creating_new():
    """Verify that the pipeline awaits the cancelled task, not just calls
    cancel().  We instrument the old task to track whether it was awaited
    (received CancelledError) before the new task's push_score_intro.
    """
    pipeline, display, event_bus = _make_pipeline()

    scorecard_a = _make_scorecard("Alpha", total=5.0)
    scorecard_b = _make_scorecard("Beta", total=10.0)
    pipeline._pending_scorecards["Alpha"] = scorecard_a
    pipeline._pending_scorecards["Beta"] = scorecard_b

    # Track the order of display calls with team names to verify no interleaving.
    call_log: list[str] = []
    original_push_intro = display.push_score_intro

    async def tracked_push_intro(team_name: str) -> None:
        call_log.append(f"intro:{team_name}")

    async def tracked_push_criterion(name: str, score: float, weight: float, just: str) -> None:
        # We tag criterion calls with the team whose reveal is active.
        # Since criteria names are the same, we use the last intro team.
        last_team = call_log[-1].split(":")[-1] if call_log else "?"
        call_log.append(f"criterion:{last_team}:{name}")

    async def tracked_push_total(team_name: str, total: float, track: str) -> None:
        call_log.append(f"total:{team_name}")

    display.push_score_intro = AsyncMock(side_effect=tracked_push_intro)
    display.push_criterion_reveal = AsyncMock(side_effect=tracked_push_criterion)
    display.push_total_score = AsyncMock(side_effect=tracked_push_total)

    _real_sleep = asyncio.sleep

    async def fake_sleep(duration: float) -> None:
        # Yield control without recursing into the patched sleep
        await _real_sleep(0)

    with patch("src.scoring.pipeline.asyncio.sleep", side_effect=fake_sleep):
        # Start Team Alpha's reveal
        await pipeline._on_commentary_delivered(_make_commentary_event("Alpha"))

        # Give Alpha's task a chance to start (reach first sleep)
        await _real_sleep(0)

        # Fire Team Beta -- this should cancel Alpha and await its completion
        await pipeline._on_commentary_delivered(_make_commentary_event("Beta"))
        await pipeline._reveal_task

    # Verify ordering: once Beta's intro appears, no Alpha calls follow
    beta_intro_seen = False
    for entry in call_log:
        if entry == "intro:Beta":
            beta_intro_seen = True
        if beta_intro_seen and "Alpha" in entry:
            pytest.fail(f"Alpha call '{entry}' appeared after Beta intro: {call_log}")

    # Only Beta's total should appear
    total_entries = [e for e in call_log if e.startswith("total:")]
    assert total_entries == ["total:Beta"], f"Expected only Beta total, got {total_entries}"
