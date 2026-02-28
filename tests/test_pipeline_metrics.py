"""Pipeline metrics validation tests.

Verifies that timing instrumentation records latency metrics for scoring,
commentary, and reveal operations via default_metrics.get_timers().
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.event_bus import EventBus
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

_TEST_SCORECARD = DemoScorecard(
    team_name="TestTeam",
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
    gemini = MagicMock()
    gemini.get_observations.return_value = observations
    gemini.clear_observations = MagicMock()
    return gemini


def _make_mock_display() -> MagicMock:
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
    yield ("Commentary delivered.", "confident", 0)


async def _setup_and_drive(event_bus, event_collector):
    """Wire full pipeline, drive one demo, and wait for score_revealed."""
    mock_gemini = _make_mock_gemini(_TEST_OBSERVATIONS)
    mock_display = _make_mock_display()

    # Defense pipeline
    defense = DefensePipeline(api_key="test", gemini_session=mock_gemini)
    await defense.setup(event_bus)

    # Commentary pipeline
    commentary = CommentaryPipeline(api_key="test", voice_id="test")
    commentary._tts = MagicMock()
    commentary._tts.connect = AsyncMock()
    commentary._tts.speak = AsyncMock()
    commentary._tts.play_sound = AsyncMock()
    commentary._tts._connected = True
    commentary._display = mock_display
    commentary._generator.stream_sentences = _fake_stream_sentences
    await commentary.setup(event_bus)

    # Scoring pipeline
    scoring = ScoringPipeline(api_key="test", display=mock_display)
    scoring._engine.score = AsyncMock(return_value=_TEST_SCORECARD)
    scoring._store.save = AsyncMock()
    await scoring.setup(event_bus)

    # Deliberation pipeline
    deliberation = DeliberationPipeline(api_key="test", display=mock_display)
    deliberation._memory_store.save = AsyncMock()
    await deliberation.setup(event_bus)

    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        event_bus.publish(DemoStarted(team_name="TestTeam"))
        await asyncio.sleep(0)
        event_bus.publish(DemoStopped(team_name="TestTeam", duration=180.0))

        await event_collector.wait_for("score_revealed", timeout=10.0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
async def test_scoring_latency_recorded(event_bus, event_collector):
    """Scoring pipeline records scoring.latency_sec metric."""
    await _setup_and_drive(event_bus, event_collector)

    timers = default_metrics.get_timers()
    assert "scoring.latency_sec" in timers, (
        f"scoring.latency_sec not in timers: {list(timers.keys())}"
    )
    assert timers["scoring.latency_sec"]["count"] >= 1


@pytest.mark.timeout(15)
async def test_commentary_latency_recorded(event_bus, event_collector):
    """Commentary pipeline records commentary.latency_sec metric."""
    await _setup_and_drive(event_bus, event_collector)

    timers = default_metrics.get_timers()
    assert "commentary.latency_sec" in timers, (
        f"commentary.latency_sec not in timers: {list(timers.keys())}"
    )
    assert timers["commentary.latency_sec"]["count"] >= 1


@pytest.mark.timeout(15)
async def test_reveal_latency_recorded(event_bus, event_collector):
    """Scoring pipeline records reveal.latency_sec metric."""
    await _setup_and_drive(event_bus, event_collector)

    timers = default_metrics.get_timers()
    assert "reveal.latency_sec" in timers, (
        f"reveal.latency_sec not in timers: {list(timers.keys())}"
    )
    assert timers["reveal.latency_sec"]["count"] >= 1
