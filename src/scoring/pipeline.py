"""Scoring pipeline orchestrator wiring engine, store, display, and event bus.

Subscribes to observation_verified to score demos and commentary_delivered
to trigger the theatrical score reveal AFTER commentary finishes. This ensures
scores appear after Arbiter's verbal commentary, creating natural dramatic
timing (Pitfall 5 avoidance).
"""

from __future__ import annotations

import asyncio
import logging
import time

from src.capture.event_bus import EventBus
from src.commentary.display_server import DisplayServer
from src.commentary.models import CommentaryDelivered
from src.capture.models import DemoStarted
from src.defense.models import ObservationVerified
from src.resilience.metrics import default_metrics
from src.scoring.engine import ScoringEngine
from src.scoring.models import DemoScorecard, ScoreRevealed, ScoringComplete
from src.scoring.moe_engine import MoEScoringEngine
from src.scoring.store import ScoreStore

logger = logging.getLogger(__name__)


class ScoringPipeline:
    """Orchestrates scoring: engine call, persistence, and theatrical display reveal.

    Subscribes to observation_verified to score demos and commentary_delivered
    to trigger the theatrical score reveal AFTER commentary finishes.
    This ensures scores appear after Arbiter's verbal commentary, creating
    natural dramatic timing (Pitfall 5 avoidance).
    """

    def __init__(
        self,
        api_key: str,
        display: DisplayServer,
        scores_dir: str = "data/scores",
        moe_engine: MoEScoringEngine | None = None,
    ) -> None:
        self._engine = ScoringEngine(api_key=api_key)
        self._moe_engine = moe_engine
        self._store = ScoreStore(scores_dir=scores_dir)
        self._display = display
        self._pending_scorecards: dict[str, DemoScorecard] = {}
        self._pending_tracks: dict[str, str] = {}
        self._event_bus: EventBus | None = None
        self._reveal_task: asyncio.Task | None = None

    async def setup(self, event_bus: EventBus) -> None:
        """Wire the scoring pipeline into the event bus.

        Subscribes to observation_verified (triggers scoring),
        commentary_delivered (triggers theatrical reveal), and
        demo_started (cancels in-flight reveals to prevent bleed).
        """
        self._event_bus = event_bus
        event_bus.subscribe("observation_verified", self._on_observation_verified)
        event_bus.subscribe("commentary_delivered", self._on_commentary_delivered)
        event_bus.subscribe("demo_started", self._on_demo_started)
        logger.info("Scoring pipeline armed")

    def set_track(self, team_name: str, track: str) -> None:
        """Store track assignment for a team.

        Called by operator CLI when starting a demo with a track argument.
        """
        self._pending_tracks[team_name] = track

    async def _on_observation_verified(self, event: ObservationVerified) -> None:
        """Score the demo when observations are verified.

        Extracts track from pending assignments (defaults to ROGUE::AGENT),
        scores via the engine, persists via the store, and publishes
        ScoringComplete.
        """
        team_name = event.output.team_name
        track = self._pending_tracks.get(team_name, "ROGUE::AGENT")
        _scoring_start = time.monotonic()

        try:
            # Use MoE engine if available, otherwise single-model engine
            engine = self._moe_engine if self._moe_engine is not None else self._engine
            scorecard = await engine.score(event.output, track)
            self._pending_scorecards[team_name] = scorecard
            await self._store.save(scorecard)
            default_metrics.observe_seconds(
                "scoring.latency_sec", time.monotonic() - _scoring_start,
            )
            logger.info(
                "Scored team %s: %.1f (track: %s)",
                team_name,
                scorecard.total_score,
                track,
            )
        except Exception:
            logger.warning(
                "Scoring failed for team %s, no scorecard available for reveal",
                team_name,
                exc_info=True,
            )
            return

        # Publish scoring complete event
        if self._event_bus is not None:
            self._event_bus.publish(ScoringComplete(scorecard=scorecard))

    async def _on_commentary_delivered(self, event: CommentaryDelivered) -> None:
        """Trigger theatrical score reveal after commentary finishes.

        Looks up the pending scorecard for the team. If scoring hasn't
        completed yet (or failed), logs and returns. The reveal runs as
        a detached asyncio task so it does NOT block the event bus callback.
        """
        scorecard = self._pending_scorecards.pop(event.team_name, None)
        if scorecard is None:
            logger.info(
                "No scorecard ready for team %s at commentary delivery "
                "(scoring still in progress or failed)",
                event.team_name,
            )
            return

        # Cancel any prior reveal still running (prevents bleed on rapid cycling)
        if self._reveal_task is not None and not self._reveal_task.done():
            self._reveal_task.cancel()
            logger.info("Cancelled previous reveal task before starting new one")

        # Launch reveal as tracked task -- must NOT block the event bus callback
        self._reveal_task = asyncio.create_task(self._reveal_score(scorecard))

    def cancel_reveal(self) -> None:
        """Cancel any in-flight score reveal task.

        Called by the operator on reset to prevent stale score cards
        from appearing on top of the intermission screen.
        """
        if self._reveal_task is not None and not self._reveal_task.done():
            self._reveal_task.cancel()
            logger.info("Cancelled in-flight score reveal")

    async def _on_demo_started(self, event: DemoStarted) -> None:
        """Cancel in-flight score reveals when a new demo starts."""
        self.cancel_reveal()

    async def _reveal_score(self, scorecard: DemoScorecard) -> None:
        """Execute the theatrical score reveal sequence.

        Phase 1: Score intro with team name (2s pause)
        Phase 2: Each criterion revealed with 1.5s spacing
        Phase 3: Track bonus if present (1.5s pause)
        Phase 4: Total score with dramatic pause (1s before reveal)

        The entire reveal is wrapped in try/except to prevent display errors
        from crashing the pipeline.
        """
        _reveal_start = time.monotonic()
        try:
            # Phase 1: Intro
            await self._display.push_score_intro(scorecard.team_name)
            await asyncio.sleep(2.0)

            # Phase 2: Criteria
            for criterion in scorecard.criteria:
                await self._display.push_criterion_reveal(
                    criterion.name,
                    criterion.score,
                    criterion.weight,
                    criterion.justification,
                )
                await asyncio.sleep(1.5)

            # Phase 3: Track bonus
            if scorecard.track_bonus is not None:
                await self._display.push_criterion_reveal(
                    scorecard.track_bonus.name,
                    scorecard.track_bonus.score,
                    scorecard.track_bonus.weight,
                    scorecard.track_bonus.justification,
                )
                await asyncio.sleep(1.5)

            # Phase 4: Total score
            await asyncio.sleep(1.0)
            await self._display.push_total_score(
                scorecard.team_name,
                scorecard.total_score,
                scorecard.track,
            )

            # Publish score revealed event
            if self._event_bus is not None:
                default_metrics.observe_seconds(
                    "reveal.latency_sec", time.monotonic() - _reveal_start,
                )
                self._event_bus.publish(
                    ScoreRevealed(team_name=scorecard.team_name)
                )

            logger.info("Score reveal complete for team: %s", scorecard.team_name)

        except asyncio.CancelledError:
            logger.info("Score reveal cancelled for team %s", scorecard.team_name)
            raise
        except Exception:
            logger.warning(
                "Error during score reveal for team %s",
                scorecard.team_name,
                exc_info=True,
            )
