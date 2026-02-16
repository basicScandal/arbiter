"""Cartesia TTS engine with emotion control and PyAudio playback.

Streams text-to-speech audio via Cartesia WebSocket with per-sentence
emotion control. Publishes TTSSpeaking/TTSFinished events on the event
bus so the audio capture layer can mute during playback.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

import pyaudio
from cartesia import AsyncCartesia

from src.capture.event_bus import EventBus
from src.commentary.models import TTSFinished, TTSSpeaking

logger = logging.getLogger(__name__)


class TTSEngine:
    """Async TTS engine using Cartesia WebSocket and PyAudio output.

    Connects to Cartesia's streaming TTS API, sends text with per-sentence
    emotion tags, and plays back raw PCM audio through PyAudio. Publishes
    tts_speaking/tts_finished events for capture mute coordination.
    """

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        event_bus: EventBus | None = None,
    ) -> None:
        self._api_key = api_key
        self._voice_id = voice_id
        self._event_bus = event_bus
        self._client = AsyncCartesia(api_key=api_key)
        self._connection = None
        self._pyaudio: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._sample_rate = 22050
        self._connected = False

    async def connect(self) -> None:
        """Open Cartesia WebSocket connection and PyAudio output stream."""
        self._connection = await self._client.tts.websocket_connect().enter()
        self._pyaudio = pyaudio.PyAudio()
        self._stream = self._pyaudio.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self._sample_rate,
            output=True,
        )
        self._connected = True
        logger.info("TTS engine connected (sample_rate=%d)", self._sample_rate)

    async def speak(
        self,
        sentence: str,
        context_id: str,
        emotion: str = "sarcastic",
        is_continuation: bool = False,
    ) -> None:
        """Speak a single sentence with emotion control.

        Publishes TTSSpeaking before playback and TTSFinished after,
        even on failure (to avoid leaving capture permanently muted).

        Args:
            sentence: Text to synthesize.
            context_id: Cartesia context ID grouping related sentences.
            emotion: Cartesia emotion tag for generation_config.
            is_continuation: Whether this continues a prior context send.
        """
        if not self._connected:
            logger.warning("TTS engine not connected, skipping speak")
            return

        if self._event_bus:
            self._event_bus.publish(TTSSpeaking())

        try:
            ctx = self._connection.context(
                context_id=context_id,
                model_id="sonic-3",
                voice={"id": self._voice_id},
                output_format={
                    "container": "raw",
                    "encoding": "pcm_f32le",
                    "sample_rate": self._sample_rate,
                },
                generation_config={"speed": 1.1, "emotion": emotion},
            )
            await ctx.send(
                model_id="sonic-3",
                transcript=sentence,
                voice={"id": self._voice_id},
                output_format={
                    "container": "raw",
                    "encoding": "pcm_f32le",
                    "sample_rate": self._sample_rate,
                },
                continue_=is_continuation,
                generation_config={"speed": 1.1, "emotion": emotion},
            )
            await ctx.no_more_inputs()

            async for event in ctx.receive():
                if event.type == "chunk" and event.audio:
                    await asyncio.to_thread(self._stream.write, event.audio)
        except Exception:
            logger.exception("TTS speak failed for sentence: %s", sentence[:80])
        finally:
            if self._event_bus:
                self._event_bus.publish(TTSFinished())

    async def speak_commentary(
        self,
        sentences: list[str],
        emotion_map: dict[int, str] | None = None,
    ) -> None:
        """Speak a full commentary as a sequence of sentences.

        Args:
            sentences: Ordered list of sentences to speak.
            emotion_map: Optional mapping of sentence index to emotion tag.
                Defaults to "sarcastic" for unmapped sentences.
        """
        context_id = str(uuid.uuid4())[:8]
        for i, sentence in enumerate(sentences):
            emotion = (emotion_map or {}).get(i, "sarcastic")
            await self.speak(
                sentence,
                context_id,
                emotion,
                is_continuation=(i > 0),
            )

    async def close(self) -> None:
        """Close WebSocket connection and PyAudio resources."""
        if self._connection is not None:
            try:
                await self._connection.close()
            except Exception:
                logger.debug("Error closing TTS WebSocket", exc_info=True)
            self._connection = None

        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                logger.debug("Error closing PyAudio stream", exc_info=True)
            self._stream = None

        if self._pyaudio is not None:
            try:
                self._pyaudio.terminate()
            except Exception:
                logger.debug("Error terminating PyAudio", exc_info=True)
            self._pyaudio = None

        self._connected = False
        logger.info("TTS engine closed")
