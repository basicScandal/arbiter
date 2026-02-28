"""Multi-demo state accumulation tests — Phase 2 Red Team + Scoring Gauntlet.

Validates that persistent stores (MemoryStore, ScoreStore) accumulate data
correctly across multiple demos, that EventBus subscriber count remains
stable (no re-registration leak), and that health status persists across
demo cycles.
"""

from __future__ import annotations

import time

import pytest

from src.capture.event_bus import EventBus
from src.capture.models import CaptureEvent
from src.memory.models import DemoMemory
from src.memory.store import MemoryStore
from src.resilience.health import default_health
from src.scoring.models import CriterionScore, DemoScorecard
from src.scoring.store import ScoreStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_demo_memory(team: str) -> DemoMemory:
    return DemoMemory(
        team_name=team,
        track="SHADOW::VECTOR",
        observations=[f"{team} demonstrated a working prototype"],
        transcripts=[f"{team} presented their approach"],
        injection_attempts=0,
        demo_duration=180.0,
        stored_at=time.time(),
    )


def _make_scorecard(team: str) -> DemoScorecard:
    return DemoScorecard(
        team_name=team,
        track="SHADOW::VECTOR",
        criteria=[
            CriterionScore(
                name="Technical Execution",
                score=7.5,
                weight=0.4,
                justification=f"Solid work by {team}",
            ),
            CriterionScore(
                name="Innovation",
                score=6.5,
                weight=0.3,
                justification=f"Novel approach by {team}",
            ),
            CriterionScore(
                name="Demo Quality",
                score=7.0,
                weight=0.3,
                justification=f"Clear demo by {team}",
            ),
        ],
        track_bonus=None,
        total_score=7.05,
        scored_at=time.time(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_memory_store_accumulates_across_demos(tmp_path):
    """Save 5 DemoMemory objects for different teams, load_all(), assert len == 5.

    Validates that MemoryStore correctly persists and retrieves multiple
    team memories without collision or data loss.
    """
    store = MemoryStore(observations_dir=str(tmp_path / "observations"))

    teams = [f"team-{i}" for i in range(5)]
    for team in teams:
        await store.save(_make_demo_memory(team))

    all_memories = await store.load_all()
    assert len(all_memories) == 5, f"Expected 5 memories, got {len(all_memories)}"

    loaded_teams = {m.team_name for m in all_memories}
    assert loaded_teams == set(teams), f"Team mismatch: {loaded_teams} != {set(teams)}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_score_store_accumulates_across_demos(tmp_path):
    """Save 5 DemoScorecard objects, load_all(), assert len == 5.

    Validates that ScoreStore correctly persists and retrieves multiple
    team scorecards without collision or data loss.
    """
    store = ScoreStore(scores_dir=str(tmp_path / "scores"))

    teams = [f"team-{i}" for i in range(5)]
    for team in teams:
        await store.save(_make_scorecard(team))

    all_scores = await store.load_all()
    assert len(all_scores) == 5, f"Expected 5 scorecards, got {len(all_scores)}"

    loaded_teams = {s.team_name for s in all_scores}
    assert loaded_teams == set(teams), f"Team mismatch: {loaded_teams} != {set(teams)}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_bus_subscriber_count_stable(event_bus: EventBus):
    """Subscribe 3 handlers, publish 5 events, assert subscriber count stays 3.

    EventBus should not re-register handlers when events are published.
    This catches accidental subscriber duplication bugs that would cause
    handlers to fire multiple times per event.
    """
    call_counts: dict[str, int] = {"a": 0, "b": 0, "c": 0}

    async def handler_a(event: CaptureEvent) -> None:
        call_counts["a"] += 1

    async def handler_b(event: CaptureEvent) -> None:
        call_counts["b"] += 1

    async def handler_c(event: CaptureEvent) -> None:
        call_counts["c"] += 1

    event_bus.subscribe("demo_started", handler_a)
    event_bus.subscribe("demo_started", handler_b)
    event_bus.subscribe("demo_started", handler_c)

    assert len(event_bus._subscribers["demo_started"]) == 3

    for i in range(5):
        event_bus.publish(CaptureEvent(event_type="demo_started"))

    await event_bus.drain()

    # Subscriber count should not have changed
    assert len(event_bus._subscribers["demo_started"]) == 3, (
        "Subscriber count changed after publishing — possible re-registration leak"
    )

    # Each handler should have been called exactly 5 times
    for name, count in call_counts.items():
        assert count == 5, f"Handler {name} called {count} times, expected 5"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_status_persists_across_demos(event_bus: EventBus):
    """Mark service unhealthy, simulate 3 demo cycles, assert still unhealthy.

    ServiceHealth is intentionally persistent — a service marked unhealthy
    stays unhealthy until the recovery window elapses or it's explicitly
    marked healthy. Demo lifecycle events (start/stop) should NOT reset
    health status.
    """
    # Use a long recovery window so it won't elapse during the test
    default_health._recovery_window = 3600.0

    default_health.mark_unhealthy("cartesia_tts")
    assert not default_health.is_healthy("cartesia_tts"), (
        "Service should be unhealthy immediately after mark_unhealthy"
    )

    # Simulate 3 demo cycles via event bus
    for _ in range(3):
        event_bus.publish(CaptureEvent(event_type="demo_started"))
        event_bus.publish(CaptureEvent(event_type="demo_stopped"))

    await event_bus.drain()

    # Health should persist — demo events don't reset health
    assert not default_health.is_healthy("cartesia_tts"), (
        "cartesia_tts health was reset by demo lifecycle events — "
        "health should persist across demos"
    )
