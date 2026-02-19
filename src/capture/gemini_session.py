"""Gemini Live API session management with context window compression and session resumption.

Consumes media chunks (audio/video) from a shared asyncio.Queue and streams them
to Gemini 2.5 Flash via the Live API WebSocket. Receives structured text observations
and audio transcription in return. Handles GoAway messages and reconnects with stored
resumption handles for resilient long-running sessions.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time

from google import genai
from google.genai import types

from src.capture.config import CaptureConfig
from src.capture.event_bus import EventBus
from src.capture.models import MediaChunk, TranscriptReceived, TranscriptSegment

logger = logging.getLogger(__name__)


class _Backoff:
    """Simple exponential backoff tracker with reset on success.

    Args:
        initial: Starting delay in seconds.
        maximum: Cap on delay in seconds.
        multiplier: Factor to increase delay on each failure.
    """

    def __init__(self, initial: float = 1.0, maximum: float = 30.0, multiplier: float = 2.0) -> None:
        self._initial = initial
        self._maximum = maximum
        self._multiplier = multiplier
        self._current = initial

    def next_delay(self) -> float:
        """Return current delay and advance to the next one."""
        delay = self._current
        self._current = min(self._current * self._multiplier, self._maximum)
        return delay

    def reset(self) -> None:
        """Reset delay to initial value (call on successful connection)."""
        self._current = self._initial


class GeminiSession:
    """Manages a Gemini Live API session for real-time demo observation.

    Connects to the Gemini Live API with context window compression and session
    resumption enabled. Consumes MediaChunk objects from a shared queue (produced
    by camera and audio capture tasks) and sends them to Gemini. Receives text
    observations and audio transcription, publishing TranscriptReceived events
    to the event bus.

    Args:
        config: Capture layer configuration with API key and model settings.
        event_bus: Event bus for publishing transcript events.
        in_queue: Shared asyncio.Queue providing MediaChunk objects from capture tasks.
    """

    def __init__(
        self,
        config: CaptureConfig,
        event_bus: EventBus,
        in_queue: asyncio.Queue[MediaChunk],
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self.in_queue = in_queue

        self._client = genai.Client(
            api_key=config.gemini_api_key,
            http_options={"api_version": "v1beta"},
        )
        self._session: types.AsyncSession | None = None
        self._resumption_handle: str | None = None
        self._stop_event = asyncio.Event()
        self._observations: list[str] = []
        # Backoff for receive-loop errors (transient mid-session hiccups)
        self._receive_backoff = _Backoff(initial=1.0, maximum=30.0)
        # Backoff for connection-level errors (full reconnect)
        self._connect_backoff = _Backoff(initial=2.0, maximum=30.0)

    def _build_config(self) -> types.LiveConnectConfig:
        """Build the LiveConnectConfig with compression, resumption, and transcription.

        Returns:
            A LiveConnectConfig configured for AUDIO response (required by native
            audio model) with both input and output audio transcription to capture
            presenter speech and Gemini observations as text.
        """
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=(
                "You are observing a live hackathon demo. Describe what you see "
                "on screen (slides, code, demos, terminal output) and what the "
                "presenter is saying. Provide structured, factual observations. "
                "Do not speculate or editorialize."
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            context_window_compression=types.ContextWindowCompressionConfig(
                trigger_tokens=self._config.compression_trigger_tokens,
                sliding_window=types.SlidingWindow(
                    target_tokens=self._config.compression_target_tokens,
                ),
            ),
            session_resumption=types.SessionResumptionConfig(
                handle=self._resumption_handle,
            ),
        )

    async def _send_loop(self) -> None:
        """Consume media chunks from the input queue and send to Gemini.

        Routes audio and video chunks to the appropriate send_realtime_input
        method. Uses a timeout on queue.get() to periodically check the stop
        event without blocking indefinitely.
        """
        while not self._stop_event.is_set():
            try:
                msg: MediaChunk = await asyncio.wait_for(
                    self.in_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            if self._session is None:
                logger.warning("Send loop: session is None, skipping chunk")
                continue

            try:
                if msg.mime_type.startswith("audio/"):
                    await self._session.send_realtime_input(
                        audio=types.Blob(
                            data=msg.data, mime_type=msg.mime_type
                        )
                    )
                elif msg.mime_type.startswith("image/"):
                    await self._session.send_realtime_input(
                        media={
                            "mime_type": msg.mime_type,
                            "data": base64.b64encode(msg.data).decode(),
                        }
                    )
                else:
                    logger.warning(
                        "Unknown media type: %s, skipping", msg.mime_type
                    )
            except Exception:
                logger.exception("Error sending media chunk to Gemini")

    async def _receive_loop(self) -> None:
        """Receive responses from the Gemini session.

        Processes text observations, audio transcription, and session resumption
        updates. Handles server errors by logging and attempting reconnection.
        """
        while not self._stop_event.is_set():
            if self._session is None:
                await asyncio.sleep(0.5)
                continue

            try:
                turn = self._session.receive()
                async for response in turn:
                    if self._stop_event.is_set():
                        break

                    # Handle session resumption updates
                    if response.session_resumption_update:
                        update = response.session_resumption_update
                        if update.resumable and update.new_handle:
                            self._resumption_handle = update.new_handle
                            logger.debug(
                                "Updated resumption handle: %s",
                                self._resumption_handle[:20] + "...",
                            )

                    # Handle output transcription (Gemini's spoken observations as text)
                    if (
                        response.server_content
                        and response.server_content.output_transcription
                    ):
                        obs_text = (
                            response.server_content.output_transcription.text
                        )
                        if obs_text:
                            self._observations.append(obs_text)
                            logger.info(
                                "Gemini observation: %s", obs_text[:200]
                            )

                    # Handle audio input transcription (presenter speech)
                    if (
                        response.server_content
                        and response.server_content.input_transcription
                    ):
                        transcript_text = (
                            response.server_content.input_transcription.text
                        )
                        if transcript_text:
                            segment = TranscriptSegment(
                                text=transcript_text,
                                timestamp=time.time(),
                            )
                            self._event_bus.publish(
                                TranscriptReceived(segment=segment)
                            )
                            logger.info(
                                "Transcript: %s", transcript_text[:200]
                            )

                    # Handle turn completion
                    if (
                        response.server_content
                        and response.server_content.turn_complete
                    ):
                        logger.debug("Turn complete")

            except Exception:
                if self._stop_event.is_set():
                    break
                delay = self._receive_backoff.next_delay()
                logger.exception(
                    "Error in receive loop, retrying in %.1fs", delay,
                )
                await asyncio.sleep(delay)

    async def run(self) -> None:
        """Main entry point: connect to Gemini and run send/receive loops.

        Connects to the Gemini Live API using the configured model and settings.
        Runs the send and receive loops concurrently. On connection errors or
        GoAway messages, reconnects with the stored resumption handle.
        """
        self._stop_event.clear()

        while not self._stop_event.is_set():
            try:
                logger.info(
                    "Connecting to Gemini Live API (model=%s, resumption=%s)",
                    self._config.gemini_model,
                    "yes" if self._resumption_handle else "no",
                )
                async with self._client.aio.live.connect(
                    model=self._config.gemini_model,
                    config=self._build_config(),
                ) as session:
                    self._session = session
                    logger.info("Gemini Live API session established")
                    # Connection succeeded — reset both backoffs
                    self._connect_backoff.reset()
                    self._receive_backoff.reset()

                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._send_loop())
                        tg.create_task(self._receive_loop())

            except Exception as exc:
                if self._stop_event.is_set():
                    break
                delay = self._connect_backoff.next_delay()
                logger.error(
                    "Gemini session error: %s: %s",
                    type(exc).__name__,
                    exc,
                )
                logger.info(
                    "Reconnecting with resumption handle in %.1fs...", delay,
                )
                await asyncio.sleep(delay)
            finally:
                self._session = None

    async def stop(self) -> None:
        """Signal the session to stop gracefully.

        Sets the stop event which causes the send and receive loops to exit.
        """
        logger.info("Stopping Gemini session")
        self._stop_event.set()

    def get_observations(self) -> list[str]:
        """Return a copy of accumulated observations.

        Returns:
            A list of text observation strings from the current/previous demo.
        """
        return list(self._observations)

    def clear_observations(self) -> None:
        """Clear the accumulated observations list.

        Call this between demos to reset the observation buffer.
        """
        self._observations.clear()
        logger.debug("Observations cleared")
