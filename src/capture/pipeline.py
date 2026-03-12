"""Capture pipeline orchestrator that wires all components together.

Connects camera, audio, Gemini session, demo state machine, and operator CLI
into a working capture system. The pipeline manages component lifecycle: when
an operator starts a demo, capture tasks spin up and feed the Gemini session.
When they stop, tasks clean up and session data is preserved.

The pipeline is glue -- it does NOT contain business logic. It connects
components and manages their lifecycle.
"""

from __future__ import annotations

import asyncio
import logging

from src.capture.audio import AudioCapture
from src.capture.camera import CameraCapture
from src.capture.config import CaptureConfig
from src.capture.demo_machine import DemoMachine
from src.capture.event_bus import EventBus
from src.capture.event_logger import EventLogger
from src.capture.gemini_session import GeminiSession
from src.capture.models import (
    CaptureEvent,
    DemoPaused,
    DemoResumed,
    DemoStarted,
    DemoStopped,
    KeyFrameDetected,
    TranscriptReceived,
)
from src.commentary.pipeline import CommentaryPipeline
from src.defense.pipeline import DefensePipeline
from src.memory.pipeline import DeliberationPipeline
from src.operator.web import WebOperator
from src.providers import create_provider
from src.providers.base import LLMProvider
from src.resilience.circuit_breaker import GeminiCircuitBreaker
from src.resilience.metrics import default_metrics
from src.scoring.moe_engine import MoEScoringEngine
from src.scoring.pipeline import ScoringPipeline

logger = logging.getLogger(__name__)


class CapturePipeline:
    """Orchestrates the full capture layer: camera, audio, Gemini, and CLI.

    Wires all components together with a shared event bus and media queue.
    Subscribes to demo lifecycle events to start/stop capture tasks on demand.

    Args:
        config: Capture configuration with device indexes, API keys, etc.
    """

    def __init__(self, config: CaptureConfig) -> None:
        self.event_bus = EventBus()
        self.media_queue: asyncio.Queue = asyncio.Queue(maxsize=config.max_queue_size)

        self.demo_machine = DemoMachine(event_bus=self.event_bus)
        self.camera = CameraCapture(
            config=config, event_bus=self.event_bus, out_queue=self.media_queue
        )
        self.audio = AudioCapture(
            config=config, event_bus=self.event_bus, out_queue=self.media_queue
        )
        self.gemini = GeminiSession(
            config=config, event_bus=self.event_bus, in_queue=self.media_queue
        )
        self.defense = DefensePipeline(
            api_key=config.gemini_api_key, gemini_session=self.gemini
        )

        # Shared circuit breaker for Gemini availability across scoring + commentary
        self._gemini_breaker = GeminiCircuitBreaker()

        self.commentary = CommentaryPipeline(
            api_key=config.gemini_api_key,
            voice_id=config.cartesia_voice_id,
            display_host=config.display_host,
            display_port=config.display_port,
            groq_api_key=config.groq_api_key,
            circuit_breaker=self._gemini_breaker,
        )

        # Build MoE scoring providers if configured
        moe_engine: MoEScoringEngine | None = None
        if config.moe_scoring_enabled:
            providers: list[LLMProvider] = [
                create_provider("gemini", config.gemini_api_key)
            ]
            if config.anthropic_api_key:
                providers.append(create_provider("claude", config.anthropic_api_key))
            if config.openai_api_key:
                providers.append(create_provider("openai", config.openai_api_key))
            if config.groq_api_key:
                providers.append(create_provider("groq", config.groq_api_key))
            if len(providers) >= 2:
                moe_engine = MoEScoringEngine(providers)
                logger.info("MoE scoring enabled with %d providers: %s",
                    len(providers), [p.name for p in providers])
            else:
                logger.warning("MoE scoring requires 2+ providers, falling back to single-model")

        # Scoring pipeline shares the SAME DisplayServer instance from commentary.
        # Isolation requirement (SCORE-03) is about the LLM path, not the display path.
        self.scoring = ScoringPipeline(
            api_key=config.gemini_api_key,
            display=self.commentary.display_server,
            moe_engine=moe_engine,
            circuit_breaker=self._gemini_breaker,
        )
        # Deliberation pipeline shares the same DisplayServer (display isolation
        # is about LLM paths, not the broadcast channel).
        self.deliberation = DeliberationPipeline(
            api_key=config.gemini_api_key,
            display=self.commentary.display_server,
        )

        self.operator = WebOperator(
            demo_machine=self.demo_machine,
            event_bus=self.event_bus,
            display_server=self.commentary._display,
            scoring_pipeline=self.scoring,
            deliberation_pipeline=self.deliberation,
        )

        self._capture_tasks: list[asyncio.Task] = []

    async def _on_demo_started(self, event: DemoStarted) -> None:
        """React to demo start: spin up camera, audio, and Gemini tasks."""
        default_metrics.inc("demos_started")
        logger.info("Demo started for team: %s", event.team_name)

        self._capture_tasks = [
            asyncio.create_task(self.camera.run(), name="camera-capture"),
            asyncio.create_task(self.audio.run(), name="audio-capture"),
            asyncio.create_task(self.gemini.run(), name="gemini-session"),
        ]

        logger.info(
            "Capture tasks started: %s",
            [t.get_name() for t in self._capture_tasks],
        )

    async def _on_demo_stopped(self, event: DemoStopped) -> None:
        """React to demo stop: shut down capture tasks, preserve session data."""
        default_metrics.inc("demos_stopped")
        default_metrics.observe_seconds("demo_duration_sec", event.duration)
        logger.info(
            "Demo stopped for team: %s, duration: %.1fs",
            event.team_name,
            event.duration,
        )

        # Stop all capture components gracefully
        await self.camera.stop()
        await self.audio.stop()
        await self.gemini.stop()

        # Cancel and await all capture tasks
        for task in self._capture_tasks:
            if not task.done():
                task.cancel()

        for task in self._capture_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Error in capture task %s during shutdown", task.get_name())

        self._capture_tasks.clear()

        # Flush stale media chunks so the next demo starts with a clean queue
        flushed = 0
        while not self.media_queue.empty():
            try:
                self.media_queue.get_nowait()
                flushed += 1
            except asyncio.QueueEmpty:
                break
        if flushed:
            logger.info("Flushed %d stale media chunks from queue", flushed)

        # Store Gemini observations in the demo session
        session = self.demo_machine.current_session
        if session is not None:
            observations = self.gemini.get_observations()
            # Clear observations for next demo
            self.gemini.clear_observations()

            # Count key frames from the session
            key_frame_count = len(session.key_frames)
            transcript_count = len(session.transcripts)

            logger.info(
                "Demo summary — Team: %s, Duration: %.1fs, Frames: %d, Transcripts: %d, Observations: %d",
                event.team_name,
                event.duration,
                key_frame_count,
                transcript_count,
                len(observations),
            )

    async def _on_demo_paused(self, event: DemoPaused) -> None:
        """React to demo pause: mute audio and pause camera frame publishing.

        Camera device stays open (do NOT release cv2.VideoCapture) -- only
        frame publishing is suppressed via the _paused flag.
        """
        self.audio.mute()
        self.camera.pause()
        logger.info("Capture paused for team: %s", event.team_name)

    async def _on_demo_resumed(self, event: DemoResumed) -> None:
        """React to demo resume: unmute audio and resume camera frame publishing."""
        self.audio.unmute()
        self.camera.resume()
        logger.info("Capture resumed for team: %s", event.team_name)

    async def _on_key_frame(self, event: KeyFrameDetected) -> None:
        """Accumulate key frames into the current demo session."""
        session = self.demo_machine.current_session
        if session is not None:
            session.key_frames.append(event.frame)

    async def _on_transcript(self, event: TranscriptReceived) -> None:
        """Accumulate transcript segments into the current demo session."""
        session = self.demo_machine.current_session
        if session is not None:
            session.transcripts.append(event.segment)

    async def _on_tts_speaking(self, event: CaptureEvent) -> None:
        """Mute audio capture when TTS starts speaking to prevent feedback."""
        self.audio.mute()
        logger.info("Audio capture muted for TTS playback")

    async def _on_tts_finished(self, event: CaptureEvent) -> None:
        """Unmute audio capture when TTS finishes speaking.

        Does NOT unmute if the demo is paused — the pause mute takes
        precedence over TTS mute to prevent audio leaking during pause.
        """
        if self.demo_machine.current_state.id == "paused":
            logger.info("TTS finished but demo is paused — keeping audio muted")
            return
        self.audio.unmute()
        logger.info("Audio capture unmuted after TTS playback")

    async def _log_event(self, event: CaptureEvent) -> None:
        """Log all events at DEBUG level for observability."""
        logger.debug(
            "Event: %s at %.3f",
            event.event_type,
            event.timestamp,
        )

    async def run(self) -> None:
        """Start the pipeline: subscribe to events and run the operator CLI.

        This is the main entry point. It subscribes to demo lifecycle events,
        prints a startup banner, and runs the operator CLI (which blocks until
        the operator quits). On exit, any running capture tasks are cleaned up.
        """
        # Subscribe to demo lifecycle events
        self.event_bus.subscribe("demo_started", self._on_demo_started)
        self.event_bus.subscribe("demo_stopped", self._on_demo_stopped)

        # Subscribe to pause/resume events for capture suspension
        self.event_bus.subscribe("demo_paused", self._on_demo_paused)
        self.event_bus.subscribe("demo_resumed", self._on_demo_resumed)

        # Subscribe to capture events for session accumulation
        self.event_bus.subscribe("key_frame_detected", self._on_key_frame)
        self.event_bus.subscribe("transcript_received", self._on_transcript)

        # Subscribe global logger for all events
        self.event_bus.subscribe_all(self._log_event)

        # Subscribe persistent event logger for post-event replay
        self._event_logger = EventLogger()
        self.event_bus.subscribe_all(self._event_logger.on_event)

        # Subscribe to TTS events for audio capture mute coordination
        self.event_bus.subscribe("tts_speaking", self._on_tts_speaking)
        self.event_bus.subscribe("tts_finished", self._on_tts_finished)

        # Wire the defense pipeline into the event bus
        await self.defense.setup(self.event_bus)

        # Wire the commentary pipeline into the event bus
        await self.commentary.setup(self.event_bus)

        # Wire the scoring pipeline into the event bus
        await self.scoring.setup(self.event_bus)

        # Wire the deliberation pipeline into the event bus
        await self.deliberation.setup(self.event_bus)

        try:
            await self.operator.run()
        finally:
            # Clean up any running capture tasks on exit
            if self._capture_tasks:
                logger.info("Cleaning up capture tasks on exit...")
                await self.camera.stop()
                await self.audio.stop()
                await self.gemini.stop()

                for task in self._capture_tasks:
                    if not task.done():
                        task.cancel()

                for task in self._capture_tasks:
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        logger.exception(
                            "Error in capture task %s during exit cleanup",
                            task.get_name(),
                        )

                self._capture_tasks.clear()

            # Shut down commentary pipeline (TTS + display server)
            await self.commentary.close()

            # Scoring pipeline has no persistent connections to close.
            # Future phases may add cleanup here if needed.

            logger.info("Capture pipeline shut down")
