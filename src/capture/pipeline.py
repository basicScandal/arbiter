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
from src.capture.models import CaptureEvent, DemoStarted, DemoStopped
from src.operator.cli import OperatorCLI

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
        self.cli = OperatorCLI(demo_machine=self.demo_machine)

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

            print(f"\n--- Demo Summary ---")
            print(f"  Team: {event.team_name}")
            print(f"  Duration: {event.duration:.1f}s")
            print(f"  Key frames captured: {key_frame_count}")
            print(f"  Transcript segments: {transcript_count}")
            print(f"  Gemini observations: {len(observations)}")
            print(f"-------------------\n")

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

        # Subscribe global logger for all events
        self.event_bus.subscribe_all(self._log_event)

        print("=" * 40)
        print("  Arbiter Capture Layer v0.1")
        print("  Type 'help' for commands")
        print("=" * 40)
        print()

        try:
            await self.cli.run()
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

            logger.info("Capture pipeline shut down")
