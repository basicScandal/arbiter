"""End-to-end tests for the full pipeline chain.

Drives a synthetic demo through defense -> commentary -> scoring -> deliberation
via a real EventBus and asserts causal event ordering using EventCollector.
All sub-pipeline external I/O is mocked (no real Gemini, TTS, display, or file
I/O calls).

Covers requirement E2E-01: full pipeline chain wiring validation.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.event_bus import EventBus
from src.capture.models import DemoStarted, DemoStopped
from src.commentary.display_server import DisplayServer
from src.commentary.models import CommentaryDelivered
from src.defense.models import ObservationVerified, SanitizedOutput
from src.defense.pipeline import DefensePipeline
from src.commentary.pipeline import CommentaryPipeline
from src.scoring.models import CriterionScore, DemoScorecard
from src.scoring.pipeline import ScoringPipeline
from src.memory.pipeline import DeliberationPipeline
from tests.helpers.event_collector import EventCollector


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
    scorecard: DemoScorecard = _TEST_SCORECARD,
):
    """Wire all four sub-pipelines to a shared event bus with mocked I/O.

    Returns (defense, commentary, scoring, deliberation) tuple.
    """
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
async def test_full_pipeline_chain(event_bus, event_collector):
    """Drive a synthetic demo through all 4 sub-pipelines and assert causal ordering.

    Chain: demo_started -> demo_stopped -> observation_verified ->
    (parallel: commentary_delivered, scoring_complete, deliberation memory save)
    """
    mock_gemini = _make_mock_gemini(_TEST_OBSERVATIONS)
    mock_display = _make_mock_display()

    defense, commentary, scoring, deliberation = await _setup_full_pipeline(
        event_bus, mock_gemini, mock_display,
    )

    # Patch asyncio.sleep in scoring pipeline to avoid theatrical delays
    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        # Step 1: Publish demo_started to reset defense state
        event_bus.publish(DemoStarted(team_name="TestTeam"))
        await asyncio.sleep(0)

        # Step 2: Publish demo_stopped to trigger defense sanitization
        event_bus.publish(DemoStopped(team_name="TestTeam", duration=180.0))

        # Step 3: Wait for cascading events
        await event_collector.wait_for("observation_verified", timeout=5.0)
        await event_collector.wait_for("commentary_delivered", timeout=5.0)
        await event_collector.wait_for("scoring_complete", timeout=5.0)

    # Assert causal event ordering
    types = [e.event_type for e in event_collector.events]
    obs_idx = types.index("observation_verified")
    score_idx = types.index("scoring_complete")
    commentary_idx = types.index("commentary_delivered")

    assert obs_idx < score_idx, (
        "observation_verified must precede scoring_complete"
    )
    assert obs_idx < commentary_idx, (
        "observation_verified must precede commentary_delivered"
    )

    # Deliberation memory auto-saved on observation_verified
    deliberation._memory_store.save.assert_called_once()

    # Do NOT assert ordering between scoring_complete and commentary_delivered
    # -- they are parallel subscribers with non-deterministic ordering


@pytest.mark.timeout(15)
async def test_full_chain_publishes_score_revealed_after_reveal(
    event_bus, event_collector,
):
    """Verify score_revealed fires after commentary_delivered triggers the reveal.

    The scoring pipeline stores the scorecard on observation_verified, then
    when commentary_delivered fires, it pops the scorecard and launches
    _reveal_score as a detached task which publishes score_revealed.
    """
    mock_gemini = _make_mock_gemini(_TEST_OBSERVATIONS)
    mock_display = _make_mock_display()

    defense, commentary, scoring, deliberation = await _setup_full_pipeline(
        event_bus, mock_gemini, mock_display,
    )

    # Patch asyncio.sleep in scoring pipeline to avoid theatrical delays
    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        # Drive the pipeline
        event_bus.publish(DemoStarted(team_name="TestTeam"))
        await asyncio.sleep(0)

        event_bus.publish(DemoStopped(team_name="TestTeam", duration=180.0))

        # Wait for the full chain including score reveal
        await event_collector.wait_for("observation_verified", timeout=5.0)
        await event_collector.wait_for("commentary_delivered", timeout=5.0)
        await event_collector.wait_for("scoring_complete", timeout=5.0)
        await event_collector.wait_for("score_revealed", timeout=10.0)

    # Assert score_revealed appears after commentary_delivered
    types = [e.event_type for e in event_collector.events]
    commentary_idx = types.index("commentary_delivered")
    revealed_idx = types.index("score_revealed")

    assert commentary_idx < revealed_idx, (
        "score_revealed must follow commentary_delivered"
    )


@pytest.mark.timeout(15)
async def test_pipeline_chain_handles_empty_observations_gracefully(
    event_bus, event_collector,
):
    """Verify the pipeline chain handles empty observations without crashing.

    When Gemini returns no observations, observation_verified still fires
    with empty data and downstream pipelines handle it gracefully.
    """
    mock_gemini = _make_mock_gemini([])  # empty observations
    mock_display = _make_mock_display()

    defense, commentary, scoring, deliberation = await _setup_full_pipeline(
        event_bus, mock_gemini, mock_display,
    )

    # Patch asyncio.sleep in scoring pipeline to avoid theatrical delays
    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        # Drive the pipeline
        event_bus.publish(DemoStarted(team_name="TestTeam"))
        await asyncio.sleep(0)

        event_bus.publish(DemoStopped(team_name="TestTeam", duration=180.0))

        # observation_verified should still fire even with empty observations
        obs_event = await event_collector.wait_for(
            "observation_verified", timeout=5.0,
        )

    # Verify the event was published (empty observations are valid)
    assert obs_event.event_type == "observation_verified"
    assert obs_event.output.team_name == "TestTeam"
    # Empty observations after reassembly
    assert obs_event.output.observations == []


# ---------------------------------------------------------------------------
# Commentary failure: scoring must still receive commentary_delivered
# ---------------------------------------------------------------------------


async def _failing_stream_sentences(sanitized_output):
    """Async generator that raises mid-stream."""
    yield ("First sentence.", "sarcastic", 0)
    raise RuntimeError("LLM connection lost")


@pytest.mark.timeout(15)
async def test_commentary_failure_still_publishes_delivered(
    event_bus, event_collector,
):
    """When commentary generation crashes, commentary_delivered must still fire.

    This is the critical fix for issue #4: without the fallback event, the
    scoring pipeline never reveals scores because it waits on commentary_delivered.
    """
    mock_gemini = _make_mock_gemini(_TEST_OBSERVATIONS)
    mock_display = _make_mock_display()

    defense, commentary, scoring, deliberation = await _setup_full_pipeline(
        event_bus, mock_gemini, mock_display,
    )

    # Replace the stream generator with one that crashes
    commentary._generator.stream_sentences = _failing_stream_sentences

    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        event_bus.publish(DemoStarted(team_name="TestTeam"))
        await asyncio.sleep(0)

        event_bus.publish(DemoStopped(team_name="TestTeam", duration=180.0))

        # commentary_delivered MUST still fire despite the crash
        delivered = await event_collector.wait_for("commentary_delivered", timeout=5.0)

    assert delivered.team_name == "TestTeam"
    # Partial text from the one sentence before the crash
    assert "First sentence." in delivered.commentary_text


@pytest.mark.timeout(15)
async def test_commentary_failure_still_triggers_score_reveal(
    event_bus, event_collector,
):
    """Full chain: commentary crash -> fallback delivered -> score reveal fires.

    End-to-end proof that the fix unblocks the scoring pipeline.
    """
    mock_gemini = _make_mock_gemini(_TEST_OBSERVATIONS)
    mock_display = _make_mock_display()

    defense, commentary, scoring, deliberation = await _setup_full_pipeline(
        event_bus, mock_gemini, mock_display,
    )

    # Replace the stream generator with one that crashes
    commentary._generator.stream_sentences = _failing_stream_sentences

    with patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock):
        event_bus.publish(DemoStarted(team_name="TestTeam"))
        await asyncio.sleep(0)

        event_bus.publish(DemoStopped(team_name="TestTeam", duration=180.0))

        # The full chain must complete: commentary_delivered -> score_revealed
        await event_collector.wait_for("commentary_delivered", timeout=5.0)
        await event_collector.wait_for("scoring_complete", timeout=5.0)
        await event_collector.wait_for("score_revealed", timeout=10.0)

    types = [e.event_type for e in event_collector.events]
    assert types.index("commentary_delivered") < types.index("score_revealed")


async def _slow_stream_sentences(sanitized_output):
    """Async generator that hangs forever after first sentence."""
    yield ("Opening line.", "confident", 0)
    await asyncio.sleep(3600)  # simulate indefinite hang


@pytest.mark.timeout(15)
async def test_commentary_timeout_still_publishes_delivered(
    event_bus, event_collector,
):
    """When commentary generation hangs, the timeout fires and delivers partial text."""
    mock_gemini = _make_mock_gemini(_TEST_OBSERVATIONS)
    mock_display = _make_mock_display()

    defense, commentary, scoring, deliberation = await _setup_full_pipeline(
        event_bus, mock_gemini, mock_display,
    )

    # Replace the stream generator with one that hangs
    commentary._generator.stream_sentences = _slow_stream_sentences

    with (
        patch("src.scoring.pipeline.asyncio.sleep", new_callable=AsyncMock),
        patch("src.commentary.pipeline._COMMENTARY_TIMEOUT", 1),
    ):
        event_bus.publish(DemoStarted(team_name="TestTeam"))
        await asyncio.sleep(0)

        event_bus.publish(DemoStopped(team_name="TestTeam", duration=180.0))

        # commentary_delivered fires after the timeout
        delivered = await event_collector.wait_for("commentary_delivered", timeout=5.0)

    assert delivered.team_name == "TestTeam"
    # Got the partial sentence before the hang
    assert "Opening line." in delivered.commentary_text
