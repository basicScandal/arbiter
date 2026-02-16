"""macOS say command TTS fallback for offline speech.

Provides a subprocess-based fallback TTS using the macOS `say` command.
Used by TTSEngine when the primary Cartesia WebSocket connection fails.
The fallback is always safe to call -- it never raises exceptions and
degrades silently if the `say` command is unavailable.
"""

from __future__ import annotations

import asyncio
import logging
import shutil

logger = logging.getLogger(__name__)


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
            proc = await asyncio.create_subprocess_exec(
                "say",
                "-v", self._voice,
                "-r", str(self._rate),
                "--", text,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception:
            logger.exception("macOS say fallback failed")
