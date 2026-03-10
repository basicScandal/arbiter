"""Tests for the multi-tier TTS fallback system.

Covers OpenAITTSFallback, MacOSSayFallback, and FallbackChain behavior
including availability detection, error isolation, and chain ordering.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.commentary.tts_fallback import (
    FallbackChain,
    MacOSSayFallback,
    OpenAITTSFallback,
)


# ---------------------------------------------------------------------------
# OpenAITTSFallback
# ---------------------------------------------------------------------------


class TestOpenAITTSFallback:
    """Tests for OpenAI TTS fallback."""

    def test_unavailable_without_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            fb = OpenAITTSFallback()
            assert fb.available is False

    def test_unavailable_without_afplay(self):
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
            patch("shutil.which", return_value=None),
        ):
            fb = OpenAITTSFallback()
            assert fb.available is False

    def test_available_with_key_and_afplay(self):
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
            patch("shutil.which", return_value="/usr/bin/afplay"),
        ):
            fb = OpenAITTSFallback()
            assert fb.available is True

    async def test_speak_noop_when_unavailable(self):
        with patch.dict("os.environ", {}, clear=True):
            fb = OpenAITTSFallback()
            # Should return without error
            await fb.speak("hello")

    async def test_speak_calls_openai_and_afplay(self):
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
            patch("shutil.which", return_value="/usr/bin/afplay"),
        ):
            fb = OpenAITTSFallback()

        mock_response = MagicMock()
        mock_response.stream_to_file = AsyncMock()

        mock_client = MagicMock()
        mock_client.audio.speech.create = AsyncMock(return_value=mock_response)

        mock_proc = MagicMock()
        mock_proc.wait = AsyncMock(return_value=0)

        with (
            patch("openai.AsyncOpenAI", return_value=mock_client),
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc),
            patch("src.commentary.tts_fallback.Path") as mock_path_cls,
        ):
            mock_path_cls.return_value.exists.return_value = True
            mock_path_cls.return_value.unlink = MagicMock()
            await fb.speak("test text")

        mock_client.audio.speech.create.assert_called_once()

    async def test_speak_handles_api_error_gracefully(self):
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
            patch("shutil.which", return_value="/usr/bin/afplay"),
        ):
            fb = OpenAITTSFallback()

        mock_client = MagicMock()
        mock_client.audio.speech.create = AsyncMock(side_effect=RuntimeError("API error"))

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            # Should not raise
            await fb.speak("test text")


# ---------------------------------------------------------------------------
# MacOSSayFallback
# ---------------------------------------------------------------------------


class TestMacOSSayFallback:
    """Tests for macOS say fallback."""

    def test_unavailable_without_say_command(self):
        with patch("shutil.which", return_value=None):
            fb = MacOSSayFallback()
            assert fb.available is False

    def test_available_with_say_command(self):
        with patch("shutil.which", return_value="/usr/bin/say"):
            fb = MacOSSayFallback()
            assert fb.available is True

    async def test_speak_noop_when_unavailable(self):
        with patch("shutil.which", return_value=None):
            fb = MacOSSayFallback()
            await fb.speak("hello")

    async def test_speak_calls_subprocess(self):
        with patch("shutil.which", return_value="/usr/bin/say"):
            fb = MacOSSayFallback()

        mock_proc = MagicMock()
        mock_proc.wait = AsyncMock(return_value=0)

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc) as mock_exec:
            await fb.speak("hello world")

        mock_exec.assert_called_once()
        args = mock_exec.call_args[0]
        assert args[0] == "say"
        assert "hello world" in args

    async def test_speak_handles_subprocess_error(self):
        with patch("shutil.which", return_value="/usr/bin/say"):
            fb = MacOSSayFallback()

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, side_effect=OSError("no such command")):
            # Should not raise
            await fb.speak("hello")


# ---------------------------------------------------------------------------
# FallbackChain
# ---------------------------------------------------------------------------


class TestFallbackChain:
    """Tests for the fallback chain ordering and error isolation."""

    def test_available_when_any_fallback_available(self):
        fb1 = MagicMock(available=False)
        fb2 = MagicMock(available=True)
        chain = FallbackChain([fb1, fb2])
        assert chain.available is True

    def test_unavailable_when_all_unavailable(self):
        fb1 = MagicMock(available=False)
        fb2 = MagicMock(available=False)
        chain = FallbackChain([fb1, fb2])
        assert chain.available is False

    def test_available_empty_chain(self):
        chain = FallbackChain([])
        assert chain.available is False

    async def test_uses_first_available(self):
        fb1 = MagicMock(available=False, speak=AsyncMock())
        fb2 = MagicMock(available=True, speak=AsyncMock())
        fb3 = MagicMock(available=True, speak=AsyncMock())

        chain = FallbackChain([fb1, fb2, fb3])
        await chain.speak("test")

        fb1.speak.assert_not_called()
        fb2.speak.assert_called_once_with("test")
        fb3.speak.assert_not_called()

    async def test_tries_next_on_failure(self):
        fb1 = MagicMock(available=True, speak=AsyncMock(side_effect=RuntimeError("fail")))
        fb2 = MagicMock(available=True, speak=AsyncMock())

        chain = FallbackChain([fb1, fb2])
        await chain.speak("test")

        fb1.speak.assert_called_once()
        fb2.speak.assert_called_once_with("test")

    async def test_all_fail_no_crash(self):
        fb1 = MagicMock(available=True, speak=AsyncMock(side_effect=RuntimeError("fail1")))
        fb2 = MagicMock(available=True, speak=AsyncMock(side_effect=RuntimeError("fail2")))

        chain = FallbackChain([fb1, fb2])
        # Should not raise
        await chain.speak("test")

    async def test_empty_chain_speak_no_crash(self):
        chain = FallbackChain([])
        await chain.speak("test")
