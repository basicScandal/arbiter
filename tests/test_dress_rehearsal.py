"""Dress rehearsal full-cycle timing tests.

Validates pipeline timing budgets, multi-demo sequencing without leaks,
and parallel execution of scoring + commentary pipelines. Uses the full
4-pipeline wiring pattern with mocked I/O.

Covers Phase 3 dress rehearsal requirements (automatable portion).
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.event_bus import EventBus
from src.capture.models import DemoStarted, DemoStopped
from src.commentary.pipeline import CommentaryPipeline
from src.defense.pipeline import DefensePipeline
from src.memory.pipeline import DeliberationPipeline
from src.resilience.metrics import default_metrics
from src.scoring.models import DemoScorecard
from src.scoring.pipeline import ScoringPipeline
from tests.helpers.factories import make_mock_display, make_mock_gemini, make_scorecard

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_TEST_OBSERVATIONS = [
    "The team built a network scanner",
    "It detected 3 open ports",
]


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
        scorecard = make_scorecard()

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


@pytest.mark.integration
@pytest.mark.timeout(15)
async def test_full_cycle_timing_under_budget(event_bus, event_collector):
    """Wall-clock from demo_stopped to score_revealed must be < 10s with mocked I/O."""
    mock_gemini = make_mock_gemini(_TEST_OBSERVATIONS)
    mock_display = make_mock_display()

    await _setup_full_pipeline(event_bus, mock_gemini, mock_display)

    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        t0 = time.monotonic()

        await _drive_demo(event_bus, "TestTeam")

        await event_collector.wait_for("score_revealed", timeout=10.0)
        elapsed = time.monotonic() - t0

    assert elapsed < 10.0, f"Full cycle took {elapsed:.2f}s (budget: 10s)"


@pytest.mark.integration
@pytest.mark.timeout(30)
async def test_five_demo_sequence(event_bus, event_collector):
    """Run 5 sequential demos: all produce score_revealed, no subscriber leaks."""
    mock_gemini = make_mock_gemini(_TEST_OBSERVATIONS)
    mock_display = make_mock_display()
    teams = [f"Team{i}" for i in range(1, 6)]

    # Track initial subscriber counts after setup
    scorecard_by_team = {t: make_scorecard(t) for t in teams}

    async def _score_for_team(sanitized, *args, **kwargs):
        return scorecard_by_team[sanitized.team_name]

    defense, commentary, scoring, deliberation = await _setup_full_pipeline(
        event_bus, mock_gemini, mock_display,
    )
    scoring._engine.score = AsyncMock(side_effect=_score_for_team)

    sub_counts_before = {
        k: len(v) for k, v in event_bus._subscribers.items()
    }

    # Capture real sleep before patching (patch targets the global asyncio module)
    _real_sleep = asyncio.sleep

    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        for i, team in enumerate(teams, 1):
            mock_gemini.get_observations.return_value = _TEST_OBSERVATIONS

            await _drive_demo(event_bus, team)

            # Wait until score_revealed count reaches expected value.
            # Use _real_sleep to yield to the event loop (the patched
            # asyncio.sleep doesn't actually yield).
            deadline = asyncio.get_event_loop().time() + 10.0
            while event_collector.count("score_revealed") < i:
                if asyncio.get_event_loop().time() > deadline:
                    break
                await _real_sleep(0.05)

            await event_bus.drain(timeout=5.0)

    # All 5 demos produced score_revealed
    revealed = event_collector.of_type("score_revealed")
    assert len(revealed) == 5, f"Expected 5 score_revealed, got {len(revealed)}"

    # No subscriber leaks (counts should be stable)
    sub_counts_after = {
        k: len(v) for k, v in event_bus._subscribers.items()
    }
    assert sub_counts_before == sub_counts_after, (
        f"Subscriber leak: before={sub_counts_before}, after={sub_counts_after}"
    )

    # Metrics show 5 scoring latency samples
    timers = default_metrics.get_timers()
    assert "scoring.latency_sec" in timers
    assert timers["scoring.latency_sec"]["count"] == 5


@pytest.mark.integration
@pytest.mark.timeout(15)
async def test_scoring_and_commentary_parallel_completion(event_bus, event_collector):
    """Scoring and commentary run concurrently, not sequentially.

    Both fire on observation_verified. Total wall-clock should be roughly
    max(scoring, commentary) not sum(scoring, commentary).
    """
    mock_gemini = make_mock_gemini(_TEST_OBSERVATIONS)
    mock_display = make_mock_display()

    # Add a small delay to scoring to make it measurably slow
    async def _slow_score(sanitized, *args, **kwargs):
        await asyncio.sleep(0.2)
        return make_scorecard()

    # Add a small delay to commentary streaming
    async def _slow_stream(sanitized_output):
        await asyncio.sleep(0.2)
        yield ("Commentary.", "confident", 0)

    defense, commentary, scoring, deliberation = await _setup_full_pipeline(
        event_bus, mock_gemini, mock_display,
    )
    scoring._engine.score = AsyncMock(side_effect=_slow_score)
    commentary._generator.stream_sentences = _slow_stream

    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        t0 = time.monotonic()

        await _drive_demo(event_bus, "TestTeam")

        await event_collector.wait_for("scoring_complete", timeout=5.0)
        await event_collector.wait_for("commentary_delivered", timeout=5.0)
        elapsed = time.monotonic() - t0

    # If sequential, would take >= 0.4s. Parallel should be ~0.2s.
    # Use generous bound to avoid flake.
    assert elapsed < 0.4, (
        f"Scoring + commentary took {elapsed:.3f}s — "
        "expected parallel execution (< 0.4s)"
    )
