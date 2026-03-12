"""Multi-tier TTS fallback system for offline speech.

Provides multiple fallback TTS options when the primary Cartesia WebSocket fails:
1. OpenAI TTS API (high quality, requires OPENAI_API_KEY)
2. macOS say command (basic quality, macOS only)

The FallbackChain tries each fallback in order until one succeeds.
All fallbacks are safe to call -- they never raise exceptions and
degrade silently if unavailable.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class OpenAITTSFallback:
    """Fallback TTS using OpenAI's TTS API.

    High-quality neural TTS via OpenAI's tts-1 model with the "onyx" voice.
    Streams audio to a temp file and plays via macOS afplay command.

    Always safe to construct regardless of API key availability. Check the
    `available` property before relying on it -- without OPENAI_API_KEY set
    it will be False and `speak()` will silently no-op.

    Args:
        voice: OpenAI voice name (default "onyx" for deep, authoritative tone).
        model: OpenAI TTS model (default "tts-1" for lower latency).
    """

    def __init__(self, voice: str = "onyx", model: str = "tts-1") -> None:
        self._voice = voice
        self._model = model
        self._api_key = os.environ.get("OPENAI_API_KEY", "")
        self._available = bool(self._api_key) and shutil.which("afplay") is not None

    @property
    def available(self) -> bool:
        """Whether OpenAI TTS is available (API key set and afplay present)."""
        return self._available

    async def speak(self, text: str) -> None:
        """Speak text via OpenAI TTS API.

        Streams audio to a temp mp3 file and plays via afplay.
        Silently returns on any error -- the fallback must never crash.

        Args:
            text: Text to synthesize and speak.
        """
        if not self._available:
            logger.warning("OpenAI TTS not available, skipping fallback")
            return

        temp_audio = None
        try:
            # Import here to avoid hard dependency if API key not set
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self._api_key)

            # Create temp file for audio output
            fd, temp_audio = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)

            # Generate speech and stream to file
            response = await client.audio.speech.create(
                model=self._model,
                voice=self._voice,
                input=text,
            )
            await response.stream_to_file(temp_audio)

            # Play audio via afplay
            proc = await asyncio.create_subprocess_exec(
                "afplay",
                temp_audio,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

        except Exception:
            logger.exception("OpenAI TTS fallback failed")
        finally:
            # Clean up temp file
            if temp_audio and Path(temp_audio).exists():
                try:
                    Path(temp_audio).unlink()
                except Exception:
                    logger.debug("Failed to clean up temp audio file: %s", temp_audio)


class MacOSSayFallback:
    """Fallback TTS using macOS say command via asyncio subprocess.

    Always safe to construct regardless of platform. Check the `available`
    property before relying on it -- on non-macOS systems it will be False
    and `speak()` will silently no-op.

    Args:
        voice: macOS voice name (default "Alex").
        rate: Words per minute (default 210).
    """

    def __init__(self, voice: str = "Alex", rate: int = 210) -> None:
        self._voice = voice
        self._rate = rate
        self._available: bool = shutil.which("say") is not None

    @property
    def available(self) -> bool:
        """Whether the macOS say command is available on this system."""
        return self._available

    async def speak(self, text: str) -> None:
        """Speak text via macOS say command.

        Non-blocking async execution via subprocess. Silently returns
        on any error -- the fallback must never crash the caller.

        Args:
            text: Text to synthesize and speak.
        """
        if not self._available:
            logger.warning("macOS say command not available, skipping fallback")
            return

        try:
            # Strip macOS speech commands (e.g., [[rate 1]], [[volm 0.5]])
            # to prevent injected text from altering voice parameters
            cleaned = re.sub(r"\[\[.*?\]\]", "", text).strip()
            proc = await asyncio.create_subprocess_exec(
                "say",
                "-v", self._voice,
                "-r", str(self._rate),
                "--", cleaned,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception:
            logger.exception("macOS say fallback failed")


class FallbackChain:
    """Chain of TTS fallbacks that tries each in order until one succeeds.

    Provides a unified interface for multiple fallback TTS options. When speak()
    is called, tries each fallback in order until one succeeds or all fail.
    The `available` property returns True if any fallback is available.

    Args:
        fallbacks: List of fallback instances (e.g., [OpenAITTSFallback(), MacOSSayFallback()]).
    """

    def __init__(self, fallbacks: list) -> None:
        self._fallbacks = fallbacks

    @property
    def available(self) -> bool:
        """Whether at least one fallback is available."""
        return any(fb.available for fb in self._fallbacks)

    async def speak(self, text: str) -> None:
        """Try each fallback in order until one succeeds.

        Logs which fallback was used. Silently returns if all fail.

        Args:
            text: Text to synthesize and speak.
        """
        for i, fallback in enumerate(self._fallbacks):
            if not fallback.available:
                continue

            try:
                logger.info("Using fallback %d: %s", i, fallback.__class__.__name__)
                await fallback.speak(text)
                return  # Success, don't try remaining fallbacks
            except Exception:
                logger.exception("Fallback %s failed, trying next", fallback.__class__.__name__)

        logger.warning("All TTS fallbacks failed or unavailable")
