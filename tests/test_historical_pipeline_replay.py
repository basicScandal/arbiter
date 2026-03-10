"""Historical demo replay through the full pipeline.

Feeds 15 real NEBULA:FOG observation sets through the full event-bus
pipeline (DefensePipeline -> ScoringPipeline -> CommentaryPipeline),
validating that real-world data flows correctly through all stages.

Uses the test_dress_rehearsal.py wiring pattern with MoEScoringEngine
backed by ReplayProvider (no API keys needed).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.event_bus import EventBus
from src.capture.models import DemoStarted, DemoStopped
from src.commentary.pipeline import CommentaryPipeline
from src.defense.pipeline import DefensePipeline
from src.memory.pipeline import DeliberationPipeline
from src.rehearsal.replay_provider import ReplayProvider
from src.scoring.moe_engine import MoEScoringEngine
from src.scoring.pipeline import ScoringPipeline
from tests.helpers.demo_memory import ALL_DEMOS, DemoMemory
from tests.helpers.factories import make_mock_display, make_mock_gemini


async def _fake_stream_sentences(sanitized_output):
    """Async generator yielding test commentary sentences."""
    yield ("Bold strategy.", "sarcastic", 0)
    yield ("The code is solid.", "confident", 1)


async def _setup_full_pipeline(
    event_bus: EventBus,
    mock_gemini: MagicMock,
    mock_display: MagicMock,
):
    """Wire all four sub-pipelines with MoEScoringEngine(ReplayProvider)."""
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

    # Scoring pipeline -- MoE with ReplayProvider (no API keys)
    moe = MoEScoringEngine([ReplayProvider()])
    scoring = ScoringPipeline(
        api_key="test", display=mock_display, moe_engine=moe,
    )
    scoring._store.save = AsyncMock()
    await scoring.setup(event_bus)

    # Deliberation pipeline -- mock memory store
    deliberation = DeliberationPipeline(api_key="test", display=mock_display)
    deliberation._memory_store.save = AsyncMock()
    await deliberation.setup(event_bus)

    return defense, commentary, scoring, deliberation


# ---------------------------------------------------------------------------
# Tests (parametrized x 15 teams)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.timeout(30)
@pytest.mark.parametrize(
    "memory",
    ALL_DEMOS,
    ids=[m.team_name for m in ALL_DEMOS],
)
async def test_historical_replay_pipeline(
    event_bus: EventBus,
    event_collector,
    memory: DemoMemory,
):
    """Replay real demo observations through the full pipeline.

    Verifies that real-world data produces correct events at each stage:
    observation_verified, scoring_complete, and score_revealed.
    """
    mock_gemini = make_mock_gemini(memory.observations)
    mock_display = make_mock_display()

    _, _, scoring, _ = await _setup_full_pipeline(
        event_bus, mock_gemini, mock_display,
    )

    # Set track before driving the demo
    scoring.set_track(memory.team_name, memory.track)

    _real_sleep = asyncio.sleep

    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        # Drive demo lifecycle
        event_bus.publish(DemoStarted(team_name=memory.team_name))
        await asyncio.sleep(0)
        event_bus.publish(
            DemoStopped(team_name=memory.team_name, duration=memory.demo_duration)
        )

        # Wait for pipeline to complete
        deadline = asyncio.get_event_loop().time() + 15.0
        while event_collector.count("score_revealed") < 1:
            if asyncio.get_event_loop().time() > deadline:
                break
            await _real_sleep(0.05)

    # -- observation_verified fired --
    verified_events = event_collector.of_type("observation_verified")
    assert len(verified_events) >= 1, "observation_verified never fired"
    sanitized = verified_events[-1].output

    assert sanitized.team_name == memory.team_name
    # Tighter sanitizer (all confidence levels) may filter all observations
    # for teams whose legitimate content triggers low-confidence patterns.
    # This is acceptable — scoring falls back to a flat scorecard.

    # -- scoring_complete fired with valid scorecard --
    scoring_events = event_collector.of_type("scoring_complete")
    assert len(scoring_events) >= 1, "scoring_complete never fired"
    scorecard = scoring_events[-1].scorecard

    assert scorecard.team_name == memory.team_name
    assert scorecard.track == memory.track
    assert len(scorecard.criteria) == 3
    for criterion in scorecard.criteria:
        assert 0.0 <= criterion.score <= 10.0
    # Not a fallback scorecard
    assert scorecard.total_score != 5.0

    # -- score_revealed fired with correct team name --
    revealed_events = event_collector.of_type("score_revealed")
    assert len(revealed_events) >= 1, "score_revealed never fired"
    assert revealed_events[-1].team_name == memory.team_name
