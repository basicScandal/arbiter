"""Test suite for the scoring pipeline orchestrator.

Tests event wiring, scoring on observation_verified, theatrical score
reveal on commentary_delivered, failure handling, and track assignment.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.event_bus import EventBus
from src.commentary.display_server import DisplayServer
from src.commentary.models import CommentaryDelivered
from src.defense.models import ObservationVerified, SanitizedOutput
from src.scoring.models import CriterionScore, DemoScorecard, ScoringComplete, ScoreRevealed
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
def scorecard() -> DemoScorecard:
    return DemoScorecard(
        team_name="TestTeam",
        track="ROGUE::AGENT",
        criteria=[
            CriterionScore(name="Technical Execution", score=8.0, weight=0.40, justification="Solid"),
            CriterionScore(name="Innovation", score=7.0, weight=0.30, justification="Novel"),
            CriterionScore(name="Demo Quality", score=6.0, weight=0.30, justification="Good demo"),
        ],
        track_bonus=None,
        total_score=7.1,
        scored_at=1000.0,
    )


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def mock_display() -> MagicMock:
    display = MagicMock(spec=DisplayServer)
    display.push_score_intro = AsyncMock()
    display.push_criterion_reveal = AsyncMock()
    display.push_total_score = AsyncMock()
    return display


# ---------------------------------------------------------------------------
# Event wiring
# ---------------------------------------------------------------------------


class TestSetup:
    """Tests for ScoringPipeline.setup event wiring."""

    @pytest.mark.asyncio
    async def test_subscribes_to_events(self, event_bus, mock_display):
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        await pipeline.setup(event_bus)

        assert "observation_verified" in event_bus._subscribers
        assert "commentary_delivered" in event_bus._subscribers


# ---------------------------------------------------------------------------
# Scoring on observation_verified
# ---------------------------------------------------------------------------


class TestOnObservationVerified:
    """Tests for scoring triggered by observation_verified events."""

    @pytest.mark.asyncio
    async def test_scores_and_stores(self, sanitized, scorecard, event_bus, mock_display):
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        await pipeline.setup(event_bus)

        # Mock the engine to return our scorecard
        pipeline._engine.score = AsyncMock(return_value=scorecard)
        pipeline._store.save = AsyncMock()

        event = ObservationVerified(output=sanitized)
        await pipeline._on_observation_verified(event)

        pipeline._engine.score.assert_called_once_with(sanitized, "ROGUE::AGENT")
        pipeline._store.save.assert_called_once_with(scorecard)

    @pytest.mark.asyncio
    async def test_uses_assigned_track(self, sanitized, scorecard, event_bus, mock_display):
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        await pipeline.setup(event_bus)

        pipeline.set_track("TestTeam", "SHADOW::VECTOR")
        pipeline._engine.score = AsyncMock(return_value=scorecard)
        pipeline._store.save = AsyncMock()

        event = ObservationVerified(output=sanitized)
        await pipeline._on_observation_verified(event)

        pipeline._engine.score.assert_called_once_with(sanitized, "SHADOW::VECTOR")

    @pytest.mark.asyncio
    async def test_defaults_to_rogue_agent(self, sanitized, scorecard, event_bus, mock_display):
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        await pipeline.setup(event_bus)

        pipeline._engine.score = AsyncMock(return_value=scorecard)
        pipeline._store.save = AsyncMock()

        event = ObservationVerified(output=sanitized)
        await pipeline._on_observation_verified(event)

        # Default track when none assigned
        pipeline._engine.score.assert_called_once_with(sanitized, "ROGUE::AGENT")

    @pytest.mark.asyncio
    async def test_publishes_scoring_complete(self, sanitized, scorecard, event_bus, mock_display):
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        await pipeline.setup(event_bus)

        pipeline._engine.score = AsyncMock(return_value=scorecard)
        pipeline._store.save = AsyncMock()

        received: list = []

        async def on_scoring_complete(e):
            received.append(e)

        event_bus.subscribe("scoring_complete", on_scoring_complete)

        event = ObservationVerified(output=sanitized)
        await pipeline._on_observation_verified(event)

        # Yield to event loop so asyncio.create_task callbacks run
        await asyncio.sleep(0)

        assert len(received) == 1
        assert isinstance(received[0], ScoringComplete)
        assert received[0].scorecard.team_name == "TestTeam"

    @pytest.mark.asyncio
    async def test_scoring_failure_no_scorecard_pending(self, sanitized, event_bus, mock_display):
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        await pipeline.setup(event_bus)

        pipeline._engine.score = AsyncMock(side_effect=Exception("LLM error"))

        event = ObservationVerified(output=sanitized)
        await pipeline._on_observation_verified(event)

        # No scorecard should be pending
        assert "TestTeam" not in pipeline._pending_scorecards

    @pytest.mark.asyncio
    async def test_uses_moe_engine_when_available(self, sanitized, scorecard, event_bus, mock_display):
        moe = MagicMock()
        moe.score = AsyncMock(return_value=scorecard)

        pipeline = ScoringPipeline(api_key="key", display=mock_display, moe_engine=moe)
        pipeline._store.save = AsyncMock()
        await pipeline.setup(event_bus)

        event = ObservationVerified(output=sanitized)
        await pipeline._on_observation_verified(event)

        moe.score.assert_called_once()
        # Single engine should NOT be called when MoE is available
        # (pipeline selects moe_engine over engine)


# ---------------------------------------------------------------------------
# Theatrical score reveal
# ---------------------------------------------------------------------------


class TestScoreReveal:
    """Tests for the theatrical score reveal sequence."""

    @pytest.mark.asyncio
    async def test_reveal_triggered_by_commentary_delivered(
        self, sanitized, scorecard, event_bus, mock_display
    ):
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        await pipeline.setup(event_bus)

        # Simulate scoring having completed (scorecard pending)
        pipeline._pending_scorecards["TestTeam"] = scorecard

        event = CommentaryDelivered(team_name="TestTeam", commentary_text="Great demo.")
        await pipeline._on_commentary_delivered(event)

        # Give the detached task time to run
        await asyncio.sleep(0.1)

        mock_display.push_score_intro.assert_called_once_with("TestTeam")

    @pytest.mark.asyncio
    async def test_reveal_sends_all_criteria(self, mock_display, scorecard):
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        pipeline._event_bus = EventBus()

        await pipeline._reveal_score(scorecard)

        # Should push intro, then 3 criteria, then total
        assert mock_display.push_score_intro.call_count == 1
        assert mock_display.push_criterion_reveal.call_count == 3
        assert mock_display.push_total_score.call_count == 1

    @pytest.mark.asyncio
    async def test_reveal_sends_track_bonus(self, mock_display):
        scorecard = DemoScorecard(
            team_name="TestTeam",
            track="SHADOW::VECTOR",
            criteria=[
                CriterionScore(name="Technical Execution", score=8.0, weight=0.40, justification="Solid"),
            ],
            track_bonus=CriterionScore(
                name="Attack Effectiveness", score=9.0, weight=0.10, justification="Novel attack",
            ),
            total_score=4.1,
            scored_at=1000.0,
        )
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        pipeline._event_bus = EventBus()

        await pipeline._reveal_score(scorecard)

        # 1 general criterion + 1 track bonus = 2 criterion reveals
        assert mock_display.push_criterion_reveal.call_count == 2

    @pytest.mark.asyncio
    async def test_reveal_publishes_score_revealed(self, mock_display, scorecard):
        bus = EventBus()
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        pipeline._event_bus = bus

        received: list = []

        async def on_score_revealed(e):
            received.append(e)

        bus.subscribe("score_revealed", on_score_revealed)

        await pipeline._reveal_score(scorecard)

        # Yield to event loop so asyncio.create_task callbacks run
        await asyncio.sleep(0)

        assert len(received) == 1
        assert isinstance(received[0], ScoreRevealed)
        assert received[0].team_name == "TestTeam"

    @pytest.mark.asyncio
    async def test_no_scorecard_skips_reveal(self, event_bus, mock_display):
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        await pipeline.setup(event_bus)

        # No scorecard pending
        event = CommentaryDelivered(team_name="Unknown", commentary_text="Text")
        await pipeline._on_commentary_delivered(event)

        await asyncio.sleep(0.1)

        mock_display.push_score_intro.assert_not_called()

    @pytest.mark.asyncio
    async def test_reveal_display_error_does_not_crash(self, mock_display, scorecard):
        """Display errors during reveal should be caught, not crash the pipeline."""
        mock_display.push_score_intro = AsyncMock(side_effect=Exception("Display down"))
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        pipeline._event_bus = EventBus()

        # Should not raise
        await pipeline._reveal_score(scorecard)

    @pytest.mark.asyncio
    async def test_scorecard_consumed_after_reveal(self, event_bus, mock_display, scorecard):
        """Scorecard should be removed from pending after commentary_delivered triggers reveal."""
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        await pipeline.setup(event_bus)

        pipeline._pending_scorecards["TestTeam"] = scorecard

        event = CommentaryDelivered(team_name="TestTeam", commentary_text="Text")
        await pipeline._on_commentary_delivered(event)

        # Scorecard consumed (popped)
        assert "TestTeam" not in pipeline._pending_scorecards


# ---------------------------------------------------------------------------
# Track assignment
# ---------------------------------------------------------------------------


class TestTrackAssignment:
    """Tests for set_track and track lookup."""

    def test_set_and_get_track(self, mock_display):
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        pipeline.set_track("TeamA", "ZERO::PROOF")
        assert pipeline._pending_tracks["TeamA"] == "ZERO::PROOF"

    def test_overwrite_track(self, mock_display):
        pipeline = ScoringPipeline(api_key="key", display=mock_display)
        pipeline.set_track("TeamA", "ZERO::PROOF")
        pipeline.set_track("TeamA", "SENTINEL::MESH")
        assert pipeline._pending_tracks["TeamA"] == "SENTINEL::MESH"
