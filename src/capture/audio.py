"""Async microphone audio capture with mute/unmute support.

Captures 16-bit PCM audio at 16kHz mono from the system microphone using PyAudio.
Audio chunks are placed into a shared output queue for downstream consumption
(e.g., Gemini Live API session).

All blocking PyAudio calls (stream open, stream read) are wrapped with
asyncio.to_thread() to avoid blocking the event loop. The stream.read()
call naturally blocks for the chunk duration (~32ms at 512 samples / 16kHz),
so no additional sleep is needed.

Mute/unmute support allows downstream components (e.g., TTS playback in Phase 3)
to suppress microphone input during Arbiter's own speech, preventing echo feedback.
"""

from __future__ import annotations

import asyncio
import logging

import pyaudio

from src.capture.config import CaptureConfig
from src.capture.event_bus import EventBus
from src.capture.models import MediaChunk

logger = logging.getLogger(__name__)


class AudioCapture:
    """Async microphone audio capture with mute/unmute support.

    Runs as an asyncio task. Opens the configured audio input device,
    captures PCM chunks, and places them into the output queue for
    downstream consumption. When muted, audio data is read (to keep
    the stream alive) but discarded.

    Queue overflow is handled gracefully by dropping audio chunks.
    """

    def __init__(
        self,
        config: CaptureConfig,
        event_bus: EventBus,
        out_queue: asyncio.Queue,
    ) -> None:
        """Initialize audio capture.

        Args:
            config: Capture configuration with audio device, sample rate, etc.
            event_bus: Event bus (reserved for future audio-level events).
            out_queue: Bounded queue for media chunks destined for Gemini.
        """
        self._config = config
        self._event_bus = event_bus
        self._out_queue = out_queue
        self._stop_event = asyncio.Event()
        self._muted: bool = False

    def mute(self) -> None:
        """Mute audio capture. Data is still read but discarded."""
        self._muted = True
        logger.info("Audio muted")

    def unmute(self) -> None:
        """Unmute audio capture. Data will be enqueued again."""
        self._muted = False
        logger.info("Audio unmuted")

    def is_muted(self) -> bool:
        """Return whether audio capture is currently muted."""
        return self._muted

    async def run(self) -> None:
        """Main audio capture loop. Opens microphone and captures until stopped.

        Captures 16-bit PCM at the configured sample rate (default 16kHz) in mono.
        Each chunk is ~32ms of audio at 512 samples / 16kHz. The stream.read()
        call blocks naturally for the chunk duration, so no additional sleep
        is needed between reads.
        """
        self._stop_event.clear()
        self._muted = False  # Reset mute state for new demo

        logger.info(
            "Starting audio capture: %dHz, %d channels, chunk_size=%d, device=%s",
            self._config.audio_sample_rate,
            self._config.audio_channels,
            self._config.audio_chunk_size,
            self._config.audio_device_index if self._config.audio_device_index is not None else "default",
        )

        pya = pyaudio.PyAudio()

        try:
            stream = await asyncio.to_thread(
                pya.open,
                format=pyaudio.paInt16,
                channels=self._config.audio_channels,
                rate=self._config.audio_sample_rate,
                input=True,
                input_device_index=self._config.audio_device_index,
                frames_per_buffer=self._config.audio_chunk_size,
            )
        except Exception:
            pya.terminate()
            raise

        consecutive_failures = 0
        max_consecutive_failures = 10

        try:
            while not self._stop_event.is_set():
                try:
                    data = await asyncio.to_thread(
                        stream.read,
                        self._config.audio_chunk_size,
                        exception_on_overflow=False,
                    )
                except Exception as e:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(
                            "Audio read failed %d times consecutively, ending capture: %s",
                            consecutive_failures,
                            e,
                        )
                        break
                    logger.warning(
                        "Audio read error (%d/%d): %s",
                        consecutive_failures,
                        max_consecutive_failures,
                        e,
                    )
                    await asyncio.sleep(0.1)
                    continue

                consecutive_failures = 0  # Reset on successful read

                # When muted, discard audio data (keep reading to prevent buffer overflow)
                if self._muted:
                    continue

                # Create media chunk for Gemini consumption
                chunk = MediaChunk(
                    mime_type="audio/pcm",
                    data=data,
                )

                try:
                    self._out_queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    pass  # Silently drop audio chunk if queue is full
        finally:
            await asyncio.to_thread(stream.close)
            pya.terminate()
            logger.info("Audio capture stopped, stream closed")

    async def stop(self) -> None:
        """Signal the audio capture loop to stop."""
        self._stop_event.set()
        logger.info("Audio capture stop requested")
