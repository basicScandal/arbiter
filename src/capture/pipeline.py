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
from src.capture.gemini_session import GeminiSession
from src.capture.models import (
    CaptureEvent,
    DemoStarted,
    DemoStopped,
    KeyFrameDetected,
    TranscriptReceived,
)
from src.commentary.pipeline import CommentaryPipeline
from src.defense.pipeline import DefensePipeline
from src.operator.cli import OperatorCLI
from src.operator.tui import ArbiterTUI
from src.scoring.pipeline import ScoringPipeline

logger = logging.getLogger(__name__)


class CapturePipeline:
    """Orchestrates the full capture layer: camera, audio, Gemini, and CLI.

    Wires all components together with a shared event bus and media queue.
    Subscribes to demo lifecycle events to start/stop capture tasks on demand.

    Args:
        config: Capture configuration with device indexes, API keys, etc.
    """

    def __init__(self, config: CaptureConfig, use_tui: bool = True) -> None:
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
        if use_tui:
            self.operator: OperatorCLI | ArbiterTUI = ArbiterTUI(
                demo_machine=self.demo_machine, event_bus=self.event_bus
            )
        else:
            self.operator = OperatorCLI(
                demo_machine=self.demo_machine,
                event_bus=self.event_bus,
                scoring_pipeline=self.scoring,
            )
        self._use_tui = use_tui
        self.defense = DefensePipeline(
            api_key=config.gemini_api_key, gemini_session=self.gemini
        )
        self.commentary = CommentaryPipeline(
            api_key=config.gemini_api_key,
            voice_id=config.cartesia_voice_id,
            display_host=config.display_host,
            display_port=config.display_port,
        )
        # Scoring pipeline shares the SAME DisplayServer instance from commentary.
        # Isolation requirement (SCORE-03) is about the LLM path, not the display path.
        self.scoring = ScoringPipeline(
            api_key=config.gemini_api_key,
            display=self.commentary._display,
        )

        self._capture_tasks: list[asyncio.Task] = []

    async def _on_demo_started(self, event: DemoStarted) -> None:
        """React to demo start: spin up camera, audio, and Gemini tasks."""
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
        """Unmute audio capture when TTS finishes speaking."""
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

        # Subscribe to capture events for session accumulation
        self.event_bus.subscribe("key_frame_detected", self._on_key_frame)
        self.event_bus.subscribe("transcript_received", self._on_transcript)

        # Subscribe global logger for all events
        self.event_bus.subscribe_all(self._log_event)

        # Subscribe to TTS events for audio capture mute coordination
        self.event_bus.subscribe("tts_speaking", self._on_tts_speaking)
        self.event_bus.subscribe("tts_finished", self._on_tts_finished)

        # Wire the defense pipeline into the event bus
        await self.defense.setup(self.event_bus)

        # Wire the commentary pipeline into the event bus
        await self.commentary.setup(self.event_bus)

        # Wire the scoring pipeline into the event bus
        await self.scoring.setup(self.event_bus)

        if not self._use_tui:
            print("=" * 40)
            print("  Arbiter Capture Layer v0.1")
            print("  Type 'help' for commands")
            print("=" * 40)
            print()

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
