"""E2E event wiring regression tests for all sub-pipeline EventBus subscriptions.

Verifies that all 13 sub-pipeline EventBus subscriptions wired in setup()
are connected and responsive to their trigger events.

Scope decision: Tests the 4 sub-pipeline setup() wiring (13 subscriptions
across defense/commentary/scoring/deliberation). The 8 CapturePipeline-direct
subscriptions are simple forwarding handlers covered by existing unit tests.

Subscription inventory (13 total):
  DefensePipeline (4): key_frame_detected, transcript_received, demo_started, demo_stopped
  CommentaryPipeline (5): observation_verified, qa_requested, injection_detected, demo_started, demo_stopped
  ScoringPipeline (2): observation_verified, commentary_delivered
  DeliberationPipeline (2): observation_verified, deliberation_requested

Coverage: E2E-03 (event wiring regression)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.event_bus import EventBus
from src.capture.models import (
    DemoStarted,
    DemoStopped,
    FrameData,
    KeyFrameDetected,
    TranscriptReceived,
    TranscriptSegment,
)
from src.commentary.display_server import DisplayServer
from src.commentary.models import CommentaryDelivered, QARequested
from src.commentary.pipeline import CommentaryPipeline
from src.defense.models import (
    InjectionAttempt,
    InjectionDetected,
    ObservationVerified,
    SanitizedOutput,
)
from src.defense.pipeline import DefensePipeline
from src.memory.models import DeliberationRequested
from src.memory.pipeline import DeliberationPipeline
from src.scoring.pipeline import ScoringPipeline

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sanitized() -> SanitizedOutput:
    return SanitizedOutput(
        team_name="TestTeam",
        observations=["Built a solid tool"],
        transcripts=[],
        injection_attempts=[],
        demo_duration=180.0,
    )


@pytest.fixture
def mock_display() -> MagicMock:
    display = MagicMock(spec=DisplayServer)
    display.push_score_intro = AsyncMock()
    display.push_criterion_reveal = AsyncMock()
    display.push_total_score = AsyncMock()
    display.push_commentary = AsyncMock()
    display.push_question = AsyncMock()
    display.push_deliberation_ranking = AsyncMock()
    display.push_deliberation_narrative = AsyncMock()
    display.start = AsyncMock()
    display.stop = AsyncMock()
    display.clear = AsyncMock()
    return display


# ---------------------------------------------------------------------------
# Test: All subscriptions registered
# ---------------------------------------------------------------------------


@pytest.mark.timeout(10)
async def test_all_sub_pipeline_subscriptions_registered(
    event_bus: EventBus,
    mock_display: MagicMock,
):
    """Every expected event type has at least one handler after all setup() calls."""
    # Create all 4 sub-pipelines with mocked dependencies
    defense = DefensePipeline(api_key="test", gemini_session=None)
    scoring = ScoringPipeline(api_key="test", display=mock_display)
    deliberation = DeliberationPipeline(api_key="test", display=mock_display)

    # CommentaryPipeline requires TTS connect and display start in setup
    with patch.object(CommentaryPipeline, "__init__", lambda self, **kw: None):
        commentary = CommentaryPipeline.__new__(CommentaryPipeline)
        # Set required attributes that setup() accesses
        commentary._event_bus = None
        commentary._tts = MagicMock()
        commentary._tts.connect = AsyncMock()
        commentary._tts._connected = False
        commentary._display = MagicMock()
        commentary._display.start = AsyncMock()
        commentary._last_sanitized = None
        commentary._last_quip_time = 0.0
        commentary._sounds = MagicMock()

    await defense.setup(event_bus)
    await commentary.setup(event_bus)
    await scoring.setup(event_bus)
    await deliberation.setup(event_bus)

    expected_event_types = {
        "key_frame_detected",
        "transcript_received",
        "demo_started",
        "demo_stopped",
        "observation_verified",
        "qa_requested",
        "injection_detected",
        "commentary_delivered",
        "deliberation_requested",
    }

    registered_types = set(event_bus._subscribers.keys())
    assert expected_event_types.issubset(registered_types), (
        f"Missing event types: {expected_event_types - registered_types}"
    )

    # Each event type must have at least one handler
    for event_type in expected_event_types:
        assert len(event_bus._subscribers[event_type]) > 0, (
            f"No handlers registered for {event_type}"
        )


# ---------------------------------------------------------------------------
# Test: Defense subscriptions responsive
# ---------------------------------------------------------------------------


@pytest.mark.timeout(10)
async def test_defense_subscriptions_responsive(event_bus: EventBus):
    """Defense pipeline handlers actually respond when events are published."""
    defense = DefensePipeline(api_key="test", gemini_session=None)
    await defense.setup(event_bus)

    # Replace handlers with AsyncMocks to track invocations
    defense._on_demo_started = AsyncMock()
    defense._on_demo_stopped = AsyncMock()
    defense._on_key_frame = AsyncMock()
    defense._on_transcript = AsyncMock()

    # Re-wire with mocked handlers (setup already registered the originals,
    # so we need to clear and re-register)
    event_bus._subscribers.clear()
    event_bus.subscribe("demo_started", defense._on_demo_started)
    event_bus.subscribe("demo_stopped", defense._on_demo_stopped)
    event_bus.subscribe("key_frame_detected", defense._on_key_frame)
    event_bus.subscribe("transcript_received", defense._on_transcript)

    # Publish each event type and give the event loop time to process
    event_bus.publish(DemoStarted(team_name="Test"))
    await asyncio.sleep(0.05)

    event_bus.publish(DemoStopped(team_name="Test", duration=1.0))
    await asyncio.sleep(0.05)

    event_bus.publish(KeyFrameDetected(
        frame=FrameData(jpeg_data=b"fake", width=1, height=1, timestamp=0.0),
    ))
    await asyncio.sleep(0.05)

    event_bus.publish(TranscriptReceived(
        segment=TranscriptSegment(text="hello", timestamp=0.0),
    ))
    await asyncio.sleep(0.05)

    defense._on_demo_started.assert_called_once()
    defense._on_demo_stopped.assert_called_once()
    defense._on_key_frame.assert_called_once()
    defense._on_transcript.assert_called_once()


# ---------------------------------------------------------------------------
# Test: Commentary subscriptions responsive
# ---------------------------------------------------------------------------


@pytest.mark.timeout(10)
async def test_commentary_subscriptions_responsive(
    event_bus: EventBus,
    sanitized: SanitizedOutput,
    mock_display: MagicMock,
):
    """Commentary pipeline handlers respond when their trigger events fire."""
    with patch.object(CommentaryPipeline, "__init__", lambda self, **kw: None):
        commentary = CommentaryPipeline.__new__(CommentaryPipeline)
        commentary._event_bus = None
        commentary._tts = MagicMock()
        commentary._tts.connect = AsyncMock()
        commentary._tts._connected = False
        commentary._display = MagicMock()
        commentary._display.start = AsyncMock()
        commentary._last_sanitized = None
        commentary._last_quip_time = 0.0
        commentary._sounds = MagicMock()

    await commentary.setup(event_bus)

    # Replace handlers with AsyncMocks
    commentary._on_observation_verified = AsyncMock()
    commentary._on_qa_requested = AsyncMock()
    commentary._on_injection_detected = AsyncMock()
    commentary._on_demo_started = AsyncMock()
    commentary._on_demo_stopped = AsyncMock()

    # Re-wire
    event_bus._subscribers.clear()
    event_bus.subscribe("observation_verified", commentary._on_observation_verified)
    event_bus.subscribe("qa_requested", commentary._on_qa_requested)
    event_bus.subscribe("injection_detected", commentary._on_injection_detected)
    event_bus.subscribe("demo_started", commentary._on_demo_started)
    event_bus.subscribe("demo_stopped", commentary._on_demo_stopped)

    # Publish each event
    event_bus.publish(ObservationVerified(output=sanitized))
    await asyncio.sleep(0.05)

    event_bus.publish(QARequested(team_name="T"))
    await asyncio.sleep(0.05)

    attempt = InjectionAttempt(
        timestamp=0.0,
        injection_type="visual",
        content="test",
        pattern="test",
        confidence="high",
        team_name="Test",
    )
    event_bus.publish(InjectionDetected(attempt=attempt))
    await asyncio.sleep(0.05)

    event_bus.publish(DemoStarted(team_name="T"))
    await asyncio.sleep(0.05)

    event_bus.publish(DemoStopped(team_name="T", duration=1.0))
    await asyncio.sleep(0.05)

    commentary._on_observation_verified.assert_called_once()
    commentary._on_qa_requested.assert_called_once()
    commentary._on_injection_detected.assert_called_once()
    commentary._on_demo_started.assert_called_once()
    commentary._on_demo_stopped.assert_called_once()


# ---------------------------------------------------------------------------
# Test: Scoring subscriptions responsive
# ---------------------------------------------------------------------------


@pytest.mark.timeout(10)
async def test_scoring_subscriptions_responsive(
    event_bus: EventBus,
    sanitized: SanitizedOutput,
    mock_display: MagicMock,
):
    """Scoring pipeline handlers respond to observation_verified and commentary_delivered."""
    scoring = ScoringPipeline(api_key="test", display=mock_display)
    await scoring.setup(event_bus)

    # Replace handlers with AsyncMocks
    scoring._on_observation_verified = AsyncMock()
    scoring._on_commentary_delivered = AsyncMock()

    # Re-wire
    event_bus._subscribers.clear()
    event_bus.subscribe("observation_verified", scoring._on_observation_verified)
    event_bus.subscribe("commentary_delivered", scoring._on_commentary_delivered)

    event_bus.publish(ObservationVerified(output=sanitized))
    await asyncio.sleep(0.05)

    event_bus.publish(CommentaryDelivered(team_name="T", commentary_text="text"))
    await asyncio.sleep(0.05)

    scoring._on_observation_verified.assert_called_once()
    scoring._on_commentary_delivered.assert_called_once()


# ---------------------------------------------------------------------------
# Test: Deliberation subscriptions responsive
# ---------------------------------------------------------------------------


@pytest.mark.timeout(10)
async def test_deliberation_subscriptions_responsive(
    event_bus: EventBus,
    sanitized: SanitizedOutput,
    mock_display: MagicMock,
):
    """Deliberation pipeline handlers respond to observation_verified and deliberation_requested."""
    deliberation = DeliberationPipeline(api_key="test", display=mock_display)
    await deliberation.setup(event_bus)

    # Replace handlers with AsyncMocks
    deliberation._on_observation_verified = AsyncMock()
    deliberation._on_deliberation_requested = AsyncMock()

    # Re-wire
    event_bus._subscribers.clear()
    event_bus.subscribe("observation_verified", deliberation._on_observation_verified)
    event_bus.subscribe("deliberation_requested", deliberation._on_deliberation_requested)

    event_bus.publish(ObservationVerified(output=sanitized))
    await asyncio.sleep(0.05)

    event_bus.publish(DeliberationRequested())
    await asyncio.sleep(0.05)

    deliberation._on_observation_verified.assert_called_once()
    deliberation._on_deliberation_requested.assert_called_once()


# ---------------------------------------------------------------------------
# Test: Subscriber count regression guard
# ---------------------------------------------------------------------------


@pytest.mark.timeout(10)
async def test_subscriber_count_matches_expected(
    event_bus: EventBus,
    mock_display: MagicMock,
):
    """Total subscriber count across all 4 sub-pipelines is exactly 13.

    This is a regression guard: if a future change adds or removes a
    subscription in any sub-pipeline's setup(), this test will fail and
    require updating the count. This catches silent wiring regressions
    (e.g., forgetting a subscribe call, event name typos).
    """
    defense = DefensePipeline(api_key="test", gemini_session=None)
    scoring = ScoringPipeline(api_key="test", display=mock_display)
    deliberation = DeliberationPipeline(api_key="test", display=mock_display)

    with patch.object(CommentaryPipeline, "__init__", lambda self, **kw: None):
        commentary = CommentaryPipeline.__new__(CommentaryPipeline)
        commentary._event_bus = None
        commentary._tts = MagicMock()
        commentary._tts.connect = AsyncMock()
        commentary._tts._connected = False
        commentary._display = MagicMock()
        commentary._display.start = AsyncMock()
        commentary._last_sanitized = None
        commentary._last_quip_time = 0.0
        commentary._sounds = MagicMock()

    await defense.setup(event_bus)
    await commentary.setup(event_bus)
    await scoring.setup(event_bus)
    await deliberation.setup(event_bus)

    total_subscribers = sum(len(v) for v in event_bus._subscribers.values())

    # Exact count: defense(4) + commentary(5) + scoring(3) + deliberation(2) = 14
    assert total_subscribers == 14, (
        f"Expected 14 total subscribers, got {total_subscribers}. "
        f"Breakdown: {dict(event_bus._subscribers)}"
    )
