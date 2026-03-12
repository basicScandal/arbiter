"""Stress tests for scoring pipeline under failure conditions and circuit breaker under sustained load.

Validates circuit breaker repeated trip/recovery cycles, rapid state checks,
scoring pipeline behavior with alternating engine failures, reveal task
cancellation, commentary_delivered without pending scorecards, concurrent
score-and-reveal timing, and fallback scorecard generation under load.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.event_bus import EventBus
from src.commentary.models import CommentaryDelivered
from src.defense.models import ObservationVerified, SanitizedOutput
from src.resilience.circuit_breaker import GeminiCircuitBreaker
from src.scoring.engine import ScoringEngine
from src.scoring.models import DemoScorecard, ScoreRevealed, ScoringComplete
from src.scoring.pipeline import ScoringPipeline
from src.scoring.rubric import GENERAL_CRITERIA
from tests.helpers.factories import make_mock_display, make_scorecard

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_sanitized_output(team_name: str = "TestTeam") -> SanitizedOutput:
    return SanitizedOutput(
        team_name=team_name,
        observations=["Built a scanner", "Detected 3 ports"],
        transcripts=["We built a tool"],
        injection_attempts=[],
        demo_duration=180.0,
    )


def _make_observation_verified(team_name: str = "TestTeam") -> ObservationVerified:
    return ObservationVerified(output=_make_sanitized_output(team_name))


# ---------------------------------------------------------------------------
# Circuit breaker stress tests
# ---------------------------------------------------------------------------


class TestCircuitBreakerStress:
    """Stress tests for GeminiCircuitBreaker under sustained load."""

    def test_circuit_breaker_twenty_trips_and_recoveries(self):
        """Trip the breaker 20 times, each time recovering through half-open -> probe -> closed.

        Verifies state ends closed, _probe_in_flight is False, and cooldown
        resets to initial value after each recovery cycle.
        """
        cb = GeminiCircuitBreaker(initial_cooldown=0.01, extended_cooldown=0.02)

        for cycle in range(20):
            # Trip the breaker
            cb.trip()
            assert cb.state == "open", f"Cycle {cycle}: expected open after trip"

            # Wait for cooldown to elapse
            time.sleep(0.02)

            # Should transition to half_open
            assert cb.state == "half_open", f"Cycle {cycle}: expected half_open after cooldown"

            # Claim the probe slot
            assert cb.available is True, f"Cycle {cycle}: probe should be available"

            # Record success to recover
            cb.record_success()

            # Verify recovery
            assert cb.state == "closed", f"Cycle {cycle}: expected closed after recovery"
            assert cb._probe_in_flight is False, f"Cycle {cycle}: probe_in_flight should be False"
            assert cb._cooldown == cb._initial_cooldown, (
                f"Cycle {cycle}: cooldown should be reset to initial value"
            )

    def test_circuit_breaker_rapid_state_checks(self):
        """Call available 1000 times in a tight loop while closed.

        Verifies all return True and no state corruption occurs.
        """
        cb = GeminiCircuitBreaker()

        results = [cb.available for _ in range(1000)]

        assert all(results), "All 1000 available checks should return True when closed"
        assert cb.state == "closed", "State should remain closed"
        assert cb._probe_in_flight is False, "No probe should be in flight"


# ---------------------------------------------------------------------------
# Scoring pipeline stress tests
# ---------------------------------------------------------------------------


@pytest.mark.timeout(30)
async def test_scoring_pipeline_ten_demos_with_alternating_failures(
    event_bus: EventBus, event_collector,
):
    """Wire a ScoringPipeline with mocked engine. Even demos succeed, odd demos raise.

    Verifies exactly 5 scoring_complete events, _pending_scorecards only has
    entries for successful demos, and no exceptions propagate.
    """
    mock_display = make_mock_display()
    pipeline = ScoringPipeline(api_key="test", display=mock_display)
    pipeline._store.save = AsyncMock()
    await pipeline.setup(event_bus)

    call_count = 0

    async def _alternating_score(sanitized, track="ROGUE::AGENT"):
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx % 2 != 0:
            raise ConnectionError(f"chaos: scoring down for demo {idx}")
        return make_scorecard(sanitized.team_name)

    pipeline._engine.score = AsyncMock(side_effect=_alternating_score)

    # Fire 10 observation_verified events
    for i in range(10):
        team = f"Team{i:02d}"
        event_bus.publish(_make_observation_verified(team))

    await event_bus.drain(timeout=10.0)

    # Exactly 5 scoring_complete events (even indices: 0, 2, 4, 6, 8)
    assert event_collector.count("scoring_complete") == 5

    # Pending scorecards should only contain successful demos
    successful_teams = {f"Team{i:02d}" for i in range(0, 10, 2)}
    assert set(pipeline._pending_scorecards.keys()) == successful_teams

    # No exceptions should have propagated (event bus catches them)
    assert event_bus.pending_count == 0


@pytest.mark.timeout(30)
async def test_reveal_cancel_stress(event_bus: EventBus, event_collector):
    """Start 10 reveal tasks in rapid succession, cancel each before it completes.

    Verifies no score_revealed events are published, no orphaned tasks remain,
    and _reveal_task is always properly managed.
    """
    mock_display = make_mock_display()
    pipeline = ScoringPipeline(api_key="test", display=mock_display)
    pipeline._store.save = AsyncMock()
    await pipeline.setup(event_bus)

    # Make display methods slow so we can cancel mid-reveal
    async def _slow_push(*args, **kwargs):
        await asyncio.sleep(10.0)

    mock_display.push_score_intro.side_effect = _slow_push

    for i in range(10):
        team = f"Team{i:02d}"
        scorecard = make_scorecard(team)

        # Manually inject a pending scorecard and trigger commentary_delivered
        pipeline._pending_scorecards[team] = scorecard
        event_bus.publish(CommentaryDelivered(
            team_name=team,
            commentary_text="Test commentary",
        ))
        # Let the event handler run and create the reveal task
        await asyncio.sleep(0)
        await event_bus.drain(timeout=2.0)

        # Cancel the reveal
        pipeline.cancel_reveal()

    # Let any cancellation settle
    await asyncio.sleep(0.1)

    # No score_revealed events should have been published
    assert event_collector.count("score_revealed") == 0

    # _reveal_task should be done (cancelled) or None
    if pipeline._reveal_task is not None:
        assert pipeline._reveal_task.done(), "Reveal task should be done after cancellation"


@pytest.mark.timeout(30)
async def test_scoring_pipeline_rapid_commentary_delivered(
    event_bus: EventBus, event_collector,
):
    """Fire 10 commentary_delivered events for teams without pending scorecards.

    Verifies no reveals are triggered, no exceptions, and _pending_scorecards
    stays empty.
    """
    mock_display = make_mock_display()
    pipeline = ScoringPipeline(api_key="test", display=mock_display)
    pipeline._store.save = AsyncMock()
    await pipeline.setup(event_bus)

    for i in range(10):
        team = f"Team{i:02d}"
        event_bus.publish(CommentaryDelivered(
            team_name=team,
            commentary_text="No scorecard for you",
        ))

    await event_bus.drain(timeout=5.0)

    # No reveals should have been triggered
    assert event_collector.count("score_revealed") == 0

    # No pending scorecards
    assert len(pipeline._pending_scorecards) == 0

    # No reveal task should be running
    assert pipeline._reveal_task is None

    # Display reveal methods should not have been called
    mock_display.push_score_intro.assert_not_called()
    mock_display.push_criterion_reveal.assert_not_called()
    mock_display.push_total_score.assert_not_called()


@pytest.mark.timeout(30)
async def test_concurrent_score_and_reveal(event_bus: EventBus, event_collector):
    """Start scoring for team A. While scoring is in progress, fire commentary_delivered.

    Tests two scenarios:
    1. commentary_delivered arrives before scoring completes -> no pending scorecard -> reveal skipped
    2. scoring completes before commentary_delivered -> reveal starts normally
    """
    mock_display = make_mock_display()
    pipeline = ScoringPipeline(api_key="test", display=mock_display)
    pipeline._store.save = AsyncMock()
    await pipeline.setup(event_bus)

    team_a = "TeamA"
    scorecard_a = make_scorecard(team_a)

    # --- Scenario 1: commentary_delivered arrives BEFORE scoring completes ---
    # Make scoring slow -- use a Future so we can resolve it manually
    scoring_started = asyncio.Event()
    scoring_future: asyncio.Future[DemoScorecard] = asyncio.get_event_loop().create_future()

    async def _slow_score(sanitized, track="ROGUE::AGENT"):
        scoring_started.set()
        return await scoring_future

    pipeline._engine.score = AsyncMock(side_effect=_slow_score)

    # Fire observation_verified to start scoring
    event_bus.publish(_make_observation_verified(team_a))
    await asyncio.sleep(0)

    # Wait for scoring to actually start
    await asyncio.wait_for(scoring_started.wait(), timeout=2.0)

    # Fire commentary_delivered while scoring is still in progress.
    # Call the handler directly to avoid drain deadlock (the observation_verified
    # task is still pending on the bus).
    await pipeline._on_commentary_delivered(CommentaryDelivered(
        team_name=team_a,
        commentary_text="Commentary before score",
    ))

    # No scorecard should be pending yet (scoring hasn't finished)
    # commentary_delivered should have found no pending scorecard
    assert team_a not in pipeline._pending_scorecards
    assert event_collector.count("score_revealed") == 0

    # Now let scoring complete
    scoring_future.set_result(scorecard_a)
    await event_bus.drain(timeout=5.0)

    # Scoring should have completed and scorecard is pending (no reveal yet,
    # because commentary_delivered already fired and found nothing)
    assert event_collector.count("scoring_complete") == 1
    assert team_a in pipeline._pending_scorecards
    assert event_collector.count("score_revealed") == 0

    # --- Scenario 2: scoring completes BEFORE commentary_delivered ---
    team_b = "TeamB"
    scorecard_b = make_scorecard(team_b)
    pipeline._engine.score = AsyncMock(return_value=scorecard_b)

    # Fire observation_verified and wait for scoring to complete
    event_bus.publish(_make_observation_verified(team_b))
    await event_bus.drain(timeout=5.0)

    assert event_collector.count("scoring_complete") == 2
    assert team_b in pipeline._pending_scorecards

    # Now fire commentary_delivered -- should trigger reveal
    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        event_bus.publish(CommentaryDelivered(
            team_name=team_b,
            commentary_text="Commentary after score",
        ))
        await event_bus.drain(timeout=5.0)

        # Wait for the detached reveal task to complete
        if pipeline._reveal_task is not None:
            await asyncio.wait_for(pipeline._reveal_task, timeout=5.0)
        # Let event bus process score_revealed from the reveal task
        await event_bus.drain(timeout=5.0)

    assert event_collector.count("score_revealed") == 1
    revealed = event_collector.of_type("score_revealed")
    assert revealed[0].team_name == team_b


@pytest.mark.timeout(30)
async def test_fallback_scorecard_under_load():
    """Call _fallback_scorecard 100 times rapidly.

    Verifies all return valid scorecards with is_fallback=True and
    total_score = 5.0.
    """
    for i in range(100):
        team = f"Team{i:02d}"
        scorecard = ScoringEngine._fallback_scorecard(
            team_name=team,
            track="ROGUE::AGENT",
            criteria=GENERAL_CRITERIA,
        )

        assert scorecard.is_fallback is True, f"Iteration {i}: should be fallback"
        assert scorecard.total_score == 5.0, (
            f"Iteration {i}: total_score should be 5.0, got {scorecard.total_score}"
        )
        assert scorecard.team_name == team
        assert scorecard.track == "ROGUE::AGENT"
        assert len(scorecard.criteria) == len(GENERAL_CRITERIA)

        # Every criterion should have score 5.0
        for criterion in scorecard.criteria:
            assert criterion.score == 5.0
            assert criterion.justification == "Scoring error -- manual review required"
