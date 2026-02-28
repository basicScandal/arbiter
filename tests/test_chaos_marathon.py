"""Phase 4: Chaos marathon sustained load tests.

Validates 20-demo sustained pipeline runs with randomized chaos injection,
asyncio task hygiene monitoring, correlated failure recovery, and combined
health signal validation. Uses the full 4-pipeline wiring pattern with
mocked I/O.

Covers Phase 4 chaos marathon requirements (automatable portion).
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.event_bus import BACKPRESSURE_THRESHOLD, EventBus
from src.capture.models import DemoStarted, DemoStopped
from src.commentary.display_server import DisplayServer
from src.commentary.pipeline import CommentaryPipeline
from src.defense.pipeline import DefensePipeline
from src.memory.pipeline import DeliberationPipeline
from src.resilience.metrics import default_metrics
from src.scoring.models import CriterionScore, DemoScorecard
from src.scoring.pipeline import ScoringPipeline


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_TEST_OBSERVATIONS = [
    "The team built a network scanner",
    "It detected 3 open ports",
]


def _make_scorecard(team_name: str = "TestTeam") -> DemoScorecard:
    return DemoScorecard(
        team_name=team_name,
        track="ROGUE::AGENT",
        criteria=[
            CriterionScore(
                name="Technical Execution", score=8.0, weight=0.40,
                justification="Solid implementation",
            ),
            CriterionScore(
                name="Innovation", score=7.0, weight=0.30,
                justification="Novel approach",
            ),
            CriterionScore(
                name="Demo Quality", score=6.0, weight=0.30,
                justification="Good presentation",
            ),
        ],
        track_bonus=None,
        total_score=7.1,
        scored_at=1000.0,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_gemini(observations: list[str]) -> MagicMock:
    """Create a mock GeminiSession returning canned observations."""
    gemini = MagicMock()
    gemini.get_observations.return_value = observations
    gemini.clear_observations = MagicMock()
    return gemini


def _make_mock_display() -> MagicMock:
    """Create a mock DisplayServer with all async methods stubbed."""
    display = MagicMock(spec=DisplayServer)
    display.start = AsyncMock()
    display.stop = AsyncMock()
    display.push_commentary = AsyncMock()
    display.push_score_intro = AsyncMock()
    display.push_criterion_reveal = AsyncMock()
    display.push_total_score = AsyncMock()
    display.push_deliberation_ranking = AsyncMock()
    display.push_deliberation_narrative = AsyncMock()
    display.clear = AsyncMock()
    return display


async def _fake_stream_sentences(sanitized_output):
    """Async generator yielding test commentary sentences."""
    yield ("Bold strategy.", "sarcastic", 0)
    yield ("The code is solid.", "confident", 1)


async def _setup_full_pipeline(
    event_bus: EventBus,
    mock_gemini: MagicMock,
    mock_display: MagicMock,
    scorecard: DemoScorecard | None = None,
):
    """Wire all four sub-pipelines to a shared event bus with mocked I/O."""
    if scorecard is None:
        scorecard = _make_scorecard()

    # Defense pipeline
    defense = DefensePipeline(api_key="test", gemini_session=mock_gemini)
    await defense.setup(event_bus)

    # Commentary pipeline -- mock TTS and display BEFORE setup()
    commentary = CommentaryPipeline(api_key="test", voice_id="test")
    commentary._tts = MagicMock()
    commentary._tts.connect = AsyncMock()
    commentary._tts.speak = AsyncMock()
    commentary._tts.play_sound = AsyncMock()
    commentary._tts._connected = True
    commentary._display = mock_display
    commentary._generator.stream_sentences = _fake_stream_sentences
    await commentary.setup(event_bus)

    # Scoring pipeline -- mock engine and store
    scoring = ScoringPipeline(api_key="test", display=mock_display)
    scoring._engine.score = AsyncMock(return_value=scorecard)
    scoring._store.save = AsyncMock()
    await scoring.setup(event_bus)

    # Deliberation pipeline -- mock memory store
    deliberation = DeliberationPipeline(api_key="test", display=mock_display)
    deliberation._memory_store.save = AsyncMock()
    await deliberation.setup(event_bus)

    return defense, commentary, scoring, deliberation


async def _drive_demo(event_bus: EventBus, team_name: str) -> None:
    """Publish demo_started then demo_stopped for a team."""
    event_bus.publish(DemoStarted(team_name=team_name))
    await asyncio.sleep(0)
    event_bus.publish(DemoStopped(team_name=team_name, duration=180.0))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

NUM_DEMOS = 20


@pytest.mark.integration
@pytest.mark.chaos
@pytest.mark.timeout(60)
async def test_twenty_demo_sustained_marathon(event_bus, event_collector):
    """20 consecutive demos through all 4 pipelines complete cleanly."""
    mock_gemini = _make_mock_gemini(_TEST_OBSERVATIONS)
    mock_display = _make_mock_display()
    teams = [f"Team{i:02d}" for i in range(1, NUM_DEMOS + 1)]

    scorecard_by_team = {t: _make_scorecard(t) for t in teams}

    async def _score_for_team(sanitized, *args, **kwargs):
        return scorecard_by_team[sanitized.team_name]

    defense, commentary, scoring, deliberation = await _setup_full_pipeline(
        event_bus, mock_gemini, mock_display,
    )
    scoring._engine.score = AsyncMock(side_effect=_score_for_team)

    sub_counts_before = {k: len(v) for k, v in event_bus._subscribers.items()}

    # Capture real sleep before patching
    _real_sleep = asyncio.sleep

    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        for i, team in enumerate(teams, 1):
            mock_gemini.get_observations.return_value = _TEST_OBSERVATIONS
            await _drive_demo(event_bus, team)

            deadline = asyncio.get_event_loop().time() + 10.0
            while event_collector.count("score_revealed") < i:
                if asyncio.get_event_loop().time() > deadline:
                    break
                await _real_sleep(0.05)

            await event_bus.drain(timeout=5.0)

    assert event_collector.count("score_revealed") == NUM_DEMOS
    assert event_collector.count("scoring_complete") == NUM_DEMOS
    assert event_collector.count("commentary_delivered") == NUM_DEMOS

    timers = default_metrics.get_timers()
    assert timers["scoring.latency_sec"]["count"] == NUM_DEMOS
    assert timers["commentary.latency_sec"]["count"] == NUM_DEMOS
    assert timers["reveal.latency_sec"]["count"] == NUM_DEMOS

    sub_counts_after = {k: len(v) for k, v in event_bus._subscribers.items()}
    assert sub_counts_before == sub_counts_after, (
        f"Subscriber leak: before={sub_counts_before}, after={sub_counts_after}"
    )

    assert default_metrics.get_counters().get("eventbus.backpressure_warning", 0) == 0


@pytest.mark.integration
@pytest.mark.chaos
@pytest.mark.timeout(60)
async def test_chaos_with_intermittent_failures(event_bus, event_collector):
    """Intermittent scoring/commentary failures across 20 demos with recovery."""
    mock_gemini = _make_mock_gemini(_TEST_OBSERVATIONS)
    mock_display = _make_mock_display()
    teams = [f"Team{i:02d}" for i in range(1, NUM_DEMOS + 1)]

    scorecard_by_team = {t: _make_scorecard(t) for t in teams}

    async def _score_for_team(sanitized, *args, **kwargs):
        return scorecard_by_team[sanitized.team_name]

    # Chaos schedule: demo index (0-based) → which component fails
    scoring_fail_demos = {2, 3, 11, 12}  # demos 3,4,12,13 (1-indexed)
    commentary_fail_demos = {7, 16}       # demos 8,17 (1-indexed)

    defense, commentary, scoring, deliberation = await _setup_full_pipeline(
        event_bus, mock_gemini, mock_display,
    )

    _healthy_score = AsyncMock(side_effect=_score_for_team)
    _healthy_stream = _fake_stream_sentences

    _real_sleep = asyncio.sleep

    expected_reveals = NUM_DEMOS - len(scoring_fail_demos)  # 16

    with (
        patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock),
        patch("src.commentary.pipeline._COMMENTARY_TIMEOUT", 1),
    ):
        for i, team in enumerate(teams):
            # Configure chaos for this demo
            if i in scoring_fail_demos:
                scoring._engine.score = AsyncMock(
                    side_effect=ConnectionError("chaos: scoring down"),
                )
            else:
                scoring._engine.score = AsyncMock(side_effect=_score_for_team)

            if i in commentary_fail_demos:
                async def _failing_stream(sanitized_output):
                    raise RuntimeError("chaos: commentary down")
                    yield  # noqa: unreachable — makes this an async generator
                commentary._generator.stream_sentences = _failing_stream
            else:
                commentary._generator.stream_sentences = _healthy_stream

            mock_gemini.get_observations.return_value = _TEST_OBSERVATIONS
            await _drive_demo(event_bus, team)

            # Wait for pipeline to settle
            deadline = asyncio.get_event_loop().time() + 10.0
            target = min(i + 1, expected_reveals) if i not in scoring_fail_demos else event_collector.count("score_revealed")
            # Just wait for commentary_delivered which always fires
            while event_collector.count("commentary_delivered") < i + 1:
                if asyncio.get_event_loop().time() > deadline:
                    break
                await _real_sleep(0.05)

            await event_bus.drain(timeout=5.0)

    assert event_collector.count("score_revealed") == expected_reveals
    assert event_collector.count("commentary_delivered") == NUM_DEMOS
    assert event_collector.count("observation_verified") == NUM_DEMOS

    timers = default_metrics.get_timers()
    assert timers["scoring.latency_sec"]["count"] == expected_reveals
    assert timers["commentary.latency_sec"]["count"] == NUM_DEMOS

    # Verify recovery: demos 5-7 (idx 4-6) after first scoring failure window
    revealed_teams = {e.team_name for e in event_collector.of_type("score_revealed")}
    for idx in [4, 5, 6]:
        assert teams[idx] in revealed_teams, f"Recovery failed: {teams[idx]} missing"
    # Demos 14-16 (idx 13-15) after second scoring failure window
    for idx in [13, 14, 15]:
        assert teams[idx] in revealed_teams, f"Recovery failed: {teams[idx]} missing"


@pytest.mark.integration
@pytest.mark.chaos
@pytest.mark.timeout(60)
async def test_asyncio_task_hygiene(event_bus, event_collector):
    """Monitor asyncio task counts across 20 demos — no leaks or backpressure."""
    mock_gemini = _make_mock_gemini(_TEST_OBSERVATIONS)
    mock_display = _make_mock_display()
    teams = [f"Team{i:02d}" for i in range(1, NUM_DEMOS + 1)]

    scorecard_by_team = {t: _make_scorecard(t) for t in teams}

    async def _score_for_team(sanitized, *args, **kwargs):
        return scorecard_by_team[sanitized.team_name]

    defense, commentary, scoring, deliberation = await _setup_full_pipeline(
        event_bus, mock_gemini, mock_display,
    )
    scoring._engine.score = AsyncMock(side_effect=_score_for_team)

    _real_sleep = asyncio.sleep
    task_counts: list[int] = []
    pending_snapshots: list[int] = []

    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        for i, team in enumerate(teams, 1):
            mock_gemini.get_observations.return_value = _TEST_OBSERVATIONS
            await _drive_demo(event_bus, team)

            deadline = asyncio.get_event_loop().time() + 10.0
            while event_collector.count("score_revealed") < i:
                if asyncio.get_event_loop().time() > deadline:
                    break
                await _real_sleep(0.05)

            await event_bus.drain(timeout=5.0)
            # Let detached _reveal_score tasks finish
            await _real_sleep(0.1)

            task_counts.append(len(asyncio.all_tasks()))
            pending_snapshots.append(event_bus.pending_count)

    assert max(task_counts) < BACKPRESSURE_THRESHOLD, (
        f"Task count {max(task_counts)} exceeded threshold {BACKPRESSURE_THRESHOLD}"
    )
    assert task_counts[-1] <= task_counts[0] + 5, (
        f"Monotonic task growth: first={task_counts[0]}, last={task_counts[-1]}"
    )
    assert all(p == 0 for p in pending_snapshots), (
        f"Event bus not fully drained: {pending_snapshots}"
    )
    assert default_metrics.get_counters().get("eventbus.backpressure_warning", 0) == 0


@pytest.mark.integration
@pytest.mark.chaos
@pytest.mark.timeout(60)
async def test_correlated_failure_kill_switch(event_bus, event_collector):
    """Total network outage (scoring+commentary) for 3 demos, then full recovery."""
    mock_gemini = _make_mock_gemini(_TEST_OBSERVATIONS)
    mock_display = _make_mock_display()
    teams = [f"Team{i:02d}" for i in range(1, NUM_DEMOS + 1)]

    scorecard_by_team = {t: _make_scorecard(t) for t in teams}

    async def _score_for_team(sanitized, *args, **kwargs):
        return scorecard_by_team[sanitized.team_name]

    outage_demos = {6, 7, 8}  # demos 7-9 (1-indexed)

    defense, commentary, scoring, deliberation = await _setup_full_pipeline(
        event_bus, mock_gemini, mock_display,
    )

    _real_sleep = asyncio.sleep
    expected_reveals = NUM_DEMOS - len(outage_demos)  # 17

    with (
        patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock),
        patch("src.commentary.pipeline._COMMENTARY_TIMEOUT", 1),
    ):
        for i, team in enumerate(teams):
            if i in outage_demos:
                scoring._engine.score = AsyncMock(
                    side_effect=ConnectionError("chaos: total outage"),
                )
                async def _outage_stream(sanitized_output):
                    raise ConnectionError("chaos: total outage")
                    yield  # noqa: unreachable
                commentary._generator.stream_sentences = _outage_stream
            else:
                scoring._engine.score = AsyncMock(side_effect=_score_for_team)
                commentary._generator.stream_sentences = _fake_stream_sentences

            mock_gemini.get_observations.return_value = _TEST_OBSERVATIONS
            await _drive_demo(event_bus, team)

            # Wait for commentary_delivered (always fires)
            deadline = asyncio.get_event_loop().time() + 10.0
            while event_collector.count("commentary_delivered") < i + 1:
                if asyncio.get_event_loop().time() > deadline:
                    break
                await _real_sleep(0.05)

            await event_bus.drain(timeout=5.0)

    assert event_collector.count("score_revealed") == expected_reveals
    assert event_collector.count("commentary_delivered") == NUM_DEMOS

    # Verify pre-outage demos succeeded
    revealed_teams = {e.team_name for e in event_collector.of_type("score_revealed")}
    for idx in range(0, 6):
        assert teams[idx] in revealed_teams, f"Pre-outage {teams[idx]} missing"

    # Verify outage demos did NOT produce score_revealed
    for idx in outage_demos:
        assert teams[idx] not in revealed_teams, f"Outage {teams[idx]} should not reveal"

    # Verify post-outage recovery
    for idx in range(9, NUM_DEMOS):
        assert teams[idx] in revealed_teams, f"Recovery {teams[idx]} missing"

    assert event_bus.pending_count == 0
    sub_counts = {k: len(v) for k, v in event_bus._subscribers.items()}
    assert all(c > 0 for c in sub_counts.values()), "Subscribers should still be registered"


@pytest.mark.integration
@pytest.mark.chaos
@pytest.mark.timeout(60)
async def test_combined_health_signals(event_bus, event_collector):
    """20 demos with 2 chaos windows — validate ALL observability signals."""
    mock_gemini = _make_mock_gemini(_TEST_OBSERVATIONS)
    mock_display = _make_mock_display()
    teams = [f"Team{i:02d}" for i in range(1, NUM_DEMOS + 1)]

    scorecard_by_team = {t: _make_scorecard(t) for t in teams}

    async def _score_for_team(sanitized, *args, **kwargs):
        return scorecard_by_team[sanitized.team_name]

    scoring_fail_demos = {3, 4}    # demos 4-5 (1-indexed)
    commentary_fail_demos = {12, 13}  # demos 13-14 (1-indexed)

    defense, commentary, scoring, deliberation = await _setup_full_pipeline(
        event_bus, mock_gemini, mock_display,
    )

    _real_sleep = asyncio.sleep
    task_snapshots: list[int] = []

    sub_counts_before = {k: len(v) for k, v in event_bus._subscribers.items()}

    expected_scores = NUM_DEMOS - len(scoring_fail_demos)  # 18

    with (
        patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock),
        patch("src.commentary.pipeline._COMMENTARY_TIMEOUT", 1),
    ):
        for i, team in enumerate(teams):
            if i in scoring_fail_demos:
                scoring._engine.score = AsyncMock(
                    side_effect=ConnectionError("chaos: scoring down"),
                )
            else:
                scoring._engine.score = AsyncMock(side_effect=_score_for_team)

            if i in commentary_fail_demos:
                async def _failing_stream(sanitized_output):
                    raise RuntimeError("chaos: commentary down")
                    yield  # noqa: unreachable
                commentary._generator.stream_sentences = _failing_stream
            else:
                commentary._generator.stream_sentences = _fake_stream_sentences

            mock_gemini.get_observations.return_value = _TEST_OBSERVATIONS
            await _drive_demo(event_bus, team)

            deadline = asyncio.get_event_loop().time() + 10.0
            while event_collector.count("commentary_delivered") < i + 1:
                if asyncio.get_event_loop().time() > deadline:
                    break
                await _real_sleep(0.05)

            await event_bus.drain(timeout=5.0)
            await _real_sleep(0.1)
            task_snapshots.append(len(asyncio.all_tasks()))

    # Event counts
    assert event_collector.count("observation_verified") == NUM_DEMOS
    assert event_collector.count("commentary_delivered") == NUM_DEMOS
    assert event_collector.count("scoring_complete") == expected_scores
    assert event_collector.count("score_revealed") == expected_scores

    # Metric timers
    timers = default_metrics.get_timers()
    assert timers["scoring.latency_sec"]["count"] == expected_scores
    assert timers["commentary.latency_sec"]["count"] == NUM_DEMOS
    assert timers["reveal.latency_sec"]["count"] == expected_scores

    # Task hygiene
    assert max(task_snapshots) < BACKPRESSURE_THRESHOLD
    assert event_bus.pending_count == 0

    # Subscriber stability
    sub_counts_after = {k: len(v) for k, v in event_bus._subscribers.items()}
    assert sub_counts_before == sub_counts_after

    # Backpressure
    assert default_metrics.get_counters().get("eventbus.backpressure_warning", 0) == 0
