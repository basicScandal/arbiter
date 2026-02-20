"""Deliberation pipeline orchestrator wiring memory, engine, display, and event bus.

Subscribes to observation_verified to auto-save per-demo memories and
deliberation_requested to run end-of-event comparative analysis. Pushes
deliberation rankings to the audience display server with theatrical pacing.

Follows the same pattern as ScoringPipeline: event-bus driven, shared
DisplayServer, try/except guards to never crash the pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from src.capture.event_bus import EventBus
from src.commentary.display_server import DisplayServer
from src.defense.models import ObservationVerified
from src.memory.deliberation_engine import DeliberationEngine
from src.memory.models import (
    DeliberationComplete,
    DeliberationRequested,
    DeliberationResult,
    DemoMemory,
)
from src.memory.store import MemoryStore
from src.scoring.store import ScoreStore

logger = logging.getLogger(__name__)


class DeliberationPipeline:
    """Orchestrates memory persistence and end-of-event deliberation.

    Auto-saves observations on each observation_verified event (MEM-01).
    Runs comparative deliberation when operator triggers deliberation_requested
    (MEM-02). Pushes rankings to audience display (MEM-03).

    Args:
        api_key: Gemini API key for the deliberation engine.
        display: Shared DisplayServer instance (same as commentary/scoring).
        scores_dir: Directory for loading authoritative scorecards.
        observations_dir: Directory for saving/loading demo memories.
        deliberation_dir: Directory for saving deliberation results.
    """

    def __init__(
        self,
        api_key: str,
        display: DisplayServer,
        scores_dir: str = "data/scores",
        observations_dir: str = "data/observations",
        deliberation_dir: str = "data/deliberation",
    ) -> None:
        self._memory_store = MemoryStore(observations_dir=observations_dir)
        self._score_store = ScoreStore(scores_dir=scores_dir)
        self._engine = DeliberationEngine(api_key=api_key)
        self._display = display
        self._deliberation_dir = Path(deliberation_dir)
        self._deliberation_dir.mkdir(parents=True, exist_ok=True)
        self._pending_tracks: dict[str, str] = {}
        self._event_bus: EventBus | None = None

    async def setup(self, event_bus: EventBus) -> None:
        """Wire the deliberation pipeline into the event bus.

        Subscribes to observation_verified (auto-save memory) and
        deliberation_requested (run comparative analysis).
        """
        self._event_bus = event_bus
        event_bus.subscribe("observation_verified", self._on_observation_verified)
        event_bus.subscribe("deliberation_requested", self._on_deliberation_requested)
        logger.info("Deliberation pipeline armed")

    def set_track(self, team_name: str, track: str) -> None:
        """Store track assignment for a team.

        Called by operator CLI when starting a demo with a track argument.
        """
        self._pending_tracks[team_name] = track

    async def _on_observation_verified(self, event: ObservationVerified) -> None:
        """Auto-save demo memory when observations are verified.

        Extracts structured data from the SanitizedOutput and persists
        as a DemoMemory via MemoryStore. Errors are logged as warnings
        but never crash the pipeline.
        """
        try:
            team_name = event.output.team_name
            track = self._pending_tracks.get(team_name, "ROGUE::AGENT")

            memory = DemoMemory(
                team_name=team_name,
                track=track,
                observations=event.output.observations,
                transcripts=event.output.transcripts,
                injection_attempts=len(event.output.injection_attempts),
                demo_duration=event.output.demo_duration,
                stored_at=time.time(),
            )

            await self._memory_store.save(memory)
            logger.info(
                "Memory saved for team %s (%d observations)",
                team_name,
                len(event.output.observations),
            )
        except Exception:
            logger.warning(
                "Failed to save memory for team %s",
                getattr(event, "output", {}) and event.output.team_name,
                exc_info=True,
            )

    async def _on_deliberation_requested(self, event: DeliberationRequested) -> None:
        """Run end-of-event comparative deliberation across all demos.

        Loads all memories and scorecards, guards against empty data and
        count mismatches, runs the deliberation engine, saves results to
        disk, and pushes rankings to the display server.
        """
        try:
            memories = await self._memory_store.load_all()
            scorecards = await self._score_store.load_all()

            # Guard: no demos recorded
            if len(memories) == 0:
                logger.warning("No demos recorded -- cannot deliberate")
                return

            # Guard: observation/score count mismatch
            if len(memories) != len(scorecards):
                logger.warning(
                    "Observation/score mismatch: %d observations, %d scorecards "
                    "-- proceeding anyway",
                    len(memories),
                    len(scorecards),
                )

            result = await self._engine.deliberate(memories, scorecards)

            # Save result to disk
            result_path = self._deliberation_dir / "result.json"
            data = json.dumps(result.model_dump(), indent=2, default=str)
            await asyncio.to_thread(result_path.write_text, data)
            logger.info("Deliberation result saved to %s", result_path)

            # Push to display as detached task (same pattern as ScoringPipeline._reveal_score)
            asyncio.create_task(self._push_deliberation_display(result))

            # Publish completion event
            if self._event_bus is not None:
                self._event_bus.publish(DeliberationComplete(result=result))

        except Exception:
            logger.error("Deliberation failed", exc_info=True)

    async def _push_deliberation_display(self, result: DeliberationResult) -> None:
        """Push deliberation rankings to audience display with theatrical pacing.

        Rankings are revealed sequentially with 2-second spacing between
        teams. After all rankings, the overall narrative is shown.
        Display errors are caught and logged -- never crash.
        """
        try:
            # Feature G: Send in reverse order for dramatic bottom-up reveal
            # (worst rank first, rank 1 / winner last)
            for ranking in reversed(result.rankings):
                await self._display.push_deliberation_ranking(
                    rank=ranking.rank,
                    team_name=ranking.team_name,
                    total_score=ranking.total_score,
                    track=ranking.track,
                    reasoning=ranking.reasoning,
                )
                await asyncio.sleep(2.0)

            await self._display.push_deliberation_narrative(result.overall_narrative)
        except Exception:
            logger.warning("Error pushing deliberation to display", exc_info=True)
