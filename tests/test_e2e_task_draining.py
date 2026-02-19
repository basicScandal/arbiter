"""End-to-end tests for multi-level asyncio.create_task chain draining.

Validates that EventCollector.wait_for() correctly handles multi-level
create_task chains dispatched by EventBus.publish(). Tests two-level chains
(observation_verified -> scoring_complete), three-level chains
(observation_verified -> commentary_delivered -> score_revealed), parallel
subscriber completion, and EventCollector's "already captured" fast path.

Covers requirement E2E-04: multi-level task draining validation.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.commentary.display_server import DisplayServer
from src.defense.models import ObservationVerified, SanitizedOutput
from src.commentary.pipeline import CommentaryPipeline
from src.scoring.models import CriterionScore, DemoScorecard
from src.scoring.pipeline import ScoringPipeline
from src.memory.pipeline import DeliberationPipeline


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_SANITIZED = SanitizedOutput(
    team_name="TestTeam",
    observations=["Built a solid network scanner"],
    transcripts=[],
    injection_attempts=[],
    demo_duration=180.0,
)

_SCORECARD = DemoScorecard(
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
async def test_two_level_chain_observation_to_scoring(event_bus, event_collector):
    """Verify two-level chain: observation_verified -> scoring_complete.

    Level 1: EventBus dispatches observation_verified handler via create_task.
    Level 2: Inside the handler, event_bus.publish(ScoringComplete) dispatches
    another create_task for ScoringComplete subscribers.
    """
    mock_display = _make_mock_display()

    scoring = ScoringPipeline(api_key="test", display=mock_display)
    scoring._engine.score = AsyncMock(return_value=_SCORECARD)
    scoring._store.save = AsyncMock()
    await scoring.setup(event_bus)

    # Publish observation_verified (Level 1 trigger)
    event_bus.publish(ObservationVerified(output=_SANITIZED))

    # Wait for the Level 2 event
    scoring_event = await event_collector.wait_for(
        "scoring_complete", timeout=5.0,
    )

    # Assert the scorecard data
    assert scoring_event.scorecard.team_name == "TestTeam"
    assert scoring_event.scorecard.total_score == 7.1

    # Assert causal ordering
    types = [e.event_type for e in event_collector.events]
    assert types.index("observation_verified") < types.index("scoring_complete")


@pytest.mark.timeout(15)
async def test_three_level_chain_observation_to_score_revealed(
    event_bus, event_collector,
):
    """Verify three-level chain: observation_verified -> commentary_delivered -> score_revealed.

    Level 1: observation_verified dispatches scoring and commentary handlers.
    Level 2: Scoring stores scorecard; commentary generates text and publishes
             commentary_delivered.
    Level 3: commentary_delivered triggers _on_commentary_delivered which pops
             the scorecard and launches _reveal_score as a detached task that
             publishes score_revealed.
    """
    mock_display = _make_mock_display()

    # Setup scoring pipeline
    scoring = ScoringPipeline(api_key="test", display=mock_display)
    scoring._engine.score = AsyncMock(return_value=_SCORECARD)
    scoring._store.save = AsyncMock()
    await scoring.setup(event_bus)

    # Setup commentary pipeline with mocked I/O
    commentary = CommentaryPipeline(api_key="test", voice_id="test")
    commentary._tts = MagicMock()
    commentary._tts.connect = AsyncMock()
    commentary._tts.speak = AsyncMock()
    commentary._tts.play_sound = AsyncMock()
    commentary._tts._connected = True
    commentary._display = mock_display
    commentary._generator.stream_sentences = _fake_stream_sentences
    await commentary.setup(event_bus)

    # Patch asyncio.sleep in scoring pipeline to skip theatrical delays
    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        # Publish the initial event
        event_bus.publish(ObservationVerified(output=_SANITIZED))

        # Wait for Level 2 events
        await event_collector.wait_for("scoring_complete", timeout=5.0)
        await event_collector.wait_for("commentary_delivered", timeout=5.0)

        # Wait for Level 3 event (detached task from _on_commentary_delivered)
        await event_collector.wait_for("score_revealed", timeout=10.0)

    # Assert full causal chain
    types = [e.event_type for e in event_collector.events]
    obs_idx = types.index("observation_verified")
    score_idx = types.index("scoring_complete")
    commentary_idx = types.index("commentary_delivered")
    revealed_idx = types.index("score_revealed")

    assert obs_idx < score_idx, (
        "observation_verified must precede scoring_complete"
    )
    assert commentary_idx < revealed_idx, (
        "commentary_delivered must precede score_revealed"
    )


@pytest.mark.timeout(15)
async def test_parallel_subscribers_all_complete(event_bus, event_collector):
    """Verify all parallel subscribers complete when observation_verified fires.

    Three pipelines subscribe to observation_verified: commentary, scoring,
    and deliberation. All three must complete their work.
    """
    mock_display = _make_mock_display()

    # Scoring pipeline
    scoring = ScoringPipeline(api_key="test", display=mock_display)
    scoring._engine.score = AsyncMock(return_value=_SCORECARD)
    scoring._store.save = AsyncMock()
    await scoring.setup(event_bus)

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

    # Deliberation pipeline
    deliberation = DeliberationPipeline(api_key="test", display=mock_display)
    deliberation._memory_store.save = AsyncMock()
    await deliberation.setup(event_bus)

    # Patch asyncio.sleep in scoring pipeline to skip theatrical delays
    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        event_bus.publish(ObservationVerified(output=_SANITIZED))

        # Wait for all three parallel subscribers
        await event_collector.wait_for("scoring_complete", timeout=5.0)
        await event_collector.wait_for("commentary_delivered", timeout=5.0)

    # All three completed
    assert event_collector.count("scoring_complete") >= 1
    assert event_collector.count("commentary_delivered") >= 1
    deliberation._memory_store.save.assert_called_once()


@pytest.mark.timeout(15)
async def test_event_collector_handles_already_captured_events(
    event_bus, event_collector,
):
    """Verify EventCollector's 'already captured' fast path.

    When wait_for() is called after the event has already been captured,
    it should return immediately without blocking.
    """
    # Publish an event
    event_bus.publish(ObservationVerified(output=_SANITIZED))

    # Yield to event loop so the event is captured by EventCollector
    await asyncio.sleep(0)

    # Verify the event was captured
    assert event_collector.count("observation_verified") == 1

    # Call wait_for AFTER capture -- should return immediately
    event = await event_collector.wait_for(
        "observation_verified", timeout=1.0,
    )

    assert event.event_type == "observation_verified"
    assert event.output.team_name == "TestTeam"
