"""Cartesia TTS engine with emotion control and PyAudio playback.

Streams text-to-speech audio via Cartesia WebSocket with per-sentence
emotion control. Publishes TTSSpeaking/TTSFinished events on the event
bus so the audio capture layer can mute during playback.
"""

from __future__ import annotations

import asyncio
import logging

import pyaudio
from cartesia import AsyncCartesia
from websockets.exceptions import ConnectionClosedOK

from src.capture.event_bus import EventBus
from src.commentary.audio_processor import AudioProcessor
from src.commentary.models import TTSFinished, TTSSpeaking
from src.commentary.tts_fallback import FallbackChain, MacOSSayFallback, OpenAITTSFallback

logger = logging.getLogger(__name__)

# Valid Cartesia emotion literals (from SDK's GenerationRequest schema).
# Used to validate emotions before sending to avoid Pydantic ValidationError.
_VALID_EMOTIONS: frozenset[str] = frozenset({
    "neutral", "happy", "excited", "enthusiastic", "elated", "euphoric",
    "triumphant", "amazed", "surprised", "flirtatious", "curious", "content",
    "peaceful", "serene", "calm", "grateful", "affectionate", "trust",
    "sympathetic", "anticipation", "mysterious", "angry", "mad", "outraged",
    "frustrated", "agitated", "threatened", "disgusted", "contempt", "envious",
    "sarcastic", "ironic", "sad", "dejected", "melancholic", "disappointed",
    "hurt", "guilty", "bored", "tired", "rejected", "nostalgic", "wistful",
    "apologetic", "hesitant", "insecure", "confused", "resigned", "anxious",
    "panicked", "alarmed", "scared", "proud", "confident", "distant",
    "skeptical", "contemplative", "determined",
})

_DEFAULT_EMOTION = "sarcastic"


def _validate_emotion(emotion: str) -> str:
    """Return the emotion if valid, otherwise fall back to default."""
    if emotion in _VALID_EMOTIONS:
        return emotion
    logger.warning("Invalid Cartesia emotion %r, falling back to %r", emotion, _DEFAULT_EMOTION)
    return _DEFAULT_EMOTION


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
        self._sample_rate = 44100
        self._connected = False
        self._closing = False
        self._cancelled = asyncio.Event()
        self._speak_lock = asyncio.Lock()
        self._fallback = FallbackChain([
            OpenAITTSFallback(),
            MacOSSayFallback(),
        ])
        self._audio_processor = AudioProcessor()

    async def connect(self) -> None:
        """Open Cartesia WebSocket connection and PyAudio output stream."""
        self._connection = await self._client.tts.websocket_connect().enter()
        self._pyaudio = pyaudio.PyAudio()
        self._stream = self._pyaudio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._sample_rate,
            output=True,
        )
        self._connected = True
        logger.info("TTS engine connected (sample_rate=%d)", self._sample_rate)

    async def _ensure_connected(self) -> bool:
        """Check connection and attempt reconnect if needed.

        Returns:
            True if connected (or reconnection succeeded), False otherwise.
        """
        if self._connected:
            return True
        try:
            await self.connect()
            return True
        except Exception:
            logger.warning("TTS reconnection failed", exc_info=True)
            return False

    async def _reconnect(self) -> bool:
        """Force reconnect after idle timeout or WebSocket close.

        Closes stale resources and opens a fresh connection.
        """
        logger.info("TTS reconnecting after idle timeout")
        self._connected = False
        try:
            if self._connection is not None:
                try:
                    await self._connection.close()
                except Exception:
                    pass
                self._connection = None
            self._connection = await self._client.tts.websocket_connect().enter()
            self._connected = True
            logger.info("TTS reconnected successfully")
            return True
        except Exception:
            logger.warning("TTS reconnection failed", exc_info=True)
            return False

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
        Falls back to macOS say command if Cartesia fails.

        Holds _speak_lock during playback so close() can wait for
        in-flight audio to finish before tearing down PyAudio.

        Args:
            sentence: Text to synthesize.
            context_id: Cartesia context ID grouping related sentences.
            emotion: Cartesia emotion tag for generation_config.
            is_continuation: Whether this continues a prior context send.
        """
        if self._closing:
            return

        # Check cancellation before acquiring the lock.
        # Flag stays set so ALL queued speaks see it — only cleared
        # by pipeline._on_observation_verified() when new commentary begins.
        if self._cancelled.is_set():
            return

        async with self._speak_lock:
            if self._closing:
                return

            # Second check after acquiring lock — a cancel() may have
            # fired while we were waiting on the lock.
            if self._cancelled.is_set():
                return

            connected = await self._ensure_connected()
            if not connected and not self._fallback.available:
                logger.warning("TTS not connected and fallback unavailable, skipping speak")
                # Still publish TTSFinished via finally block for mute coordination
                if self._event_bus:
                    self._event_bus.publish(TTSSpeaking())
                try:
                    return
                finally:
                    if self._event_bus:
                        self._event_bus.publish(TTSFinished())

            if self._event_bus:
                self._event_bus.publish(TTSSpeaking())

            try:
                if not connected:
                    raise ConnectionError("Cartesia not connected, skip to fallback")

                await self._send_to_cartesia(sentence, context_id, emotion, is_continuation)
            except ConnectionClosedOK:
                logger.warning("Cartesia WebSocket idle timeout, reconnecting...")
                if await self._reconnect():
                    try:
                        await self._send_to_cartesia(sentence, context_id, emotion, is_continuation)
                    except Exception:
                        logger.exception("TTS retry failed for sentence: %s", sentence[:80])
                        await self._try_fallback(sentence)
                else:
                    await self._try_fallback(sentence)
            except Exception:
                logger.exception("TTS speak failed for sentence: %s", sentence[:80])
                await self._try_fallback(sentence)
            finally:
                if self._event_bus:
                    self._event_bus.publish(TTSFinished())

    async def _send_to_cartesia(
        self,
        sentence: str,
        context_id: str,
        emotion: str,
        is_continuation: bool,
    ) -> None:
        """Send a sentence to Cartesia WebSocket and play audio chunks."""
        emotion = _validate_emotion(emotion)
        voice_spec = {"id": self._voice_id, "mode": "id"}
        ctx = self._connection.context(
            context_id=context_id,
            model_id="sonic-3",
            voice=voice_spec,
            output_format={
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": self._sample_rate,
            },
            generation_config={"speed": 1.1, "emotion": emotion},
        )
        await ctx.send(
            model_id="sonic-3",
            transcript=sentence,
            voice=voice_spec,
            output_format={
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": self._sample_rate,
            },
            continue_=is_continuation,
            generation_config={"speed": 1.1, "emotion": emotion},
        )
        await ctx.no_more_inputs()

        async for event in ctx.receive():
            if self._cancelled.is_set():
                logger.info("TTS cancelled mid-stream, breaking out")
                break
            if event.type == "chunk" and event.audio:
                processed = self._audio_processor.process_chunk(event.audio)
                await asyncio.to_thread(self._stream.write, processed)

    async def _try_fallback(self, sentence: str) -> None:
        """Attempt macOS say fallback for a sentence."""
        try:
            if self._fallback.available:
                logger.warning("Cartesia TTS failed, attempting macOS say fallback")
                await self._fallback.speak(sentence)
            else:
                logger.warning("macOS say fallback not available")
        except Exception:
            logger.exception("macOS say fallback also failed")

    def cancel(self) -> None:
        """Cancel pending speak() calls.

        Sets a cancellation flag checked by speak() before acquiring the
        lock. The flag is cleared on the next speak() call so the engine
        can be reused after cancellation.
        """
        self._cancelled.set()
        logger.info("TTS engine cancelled -- pending speaks will be skipped")

    async def play_sound(self, pcm_bytes: bytes) -> None:
        """Play raw PCM int16 bytes through the PyAudio stream.

        Used for sound effects (chimes, alerts). Respects _speak_lock
        and _closing flag like speak().
        """
        if self._closing or self._stream is None:
            return
        async with self._speak_lock:
            if self._closing or self._stream is None:
                return
            try:
                await asyncio.to_thread(self._stream.write, pcm_bytes)
            except Exception:
                logger.debug("Sound effect playback failed", exc_info=True)

    async def close(self) -> None:
        """Close WebSocket connection and PyAudio resources.

        Sets _closing flag to reject new speak() calls, then acquires
        _speak_lock to wait for any in-flight playback to finish before
        tearing down resources. This prevents the PortAudio error that
        occurs when the stream is destroyed mid-write.
        """
        self._closing = True

        # Wait for any in-flight speak() to finish writing audio
        async with self._speak_lock:
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
