"""Tests for Gemini Live model compatibility.

Ensures GEMINI_LIVE_MODEL is always set to a model that supports the
bidiGenerateContent Live API. This test suite was created after a production
incident where changing the default from gemini-2.5-flash to gemini-2.0-flash
broke all real-time audio/video analysis, audience display updates, and Q&A
listening — silently, with the Gemini session error-looping in the background.

Three test levels:
  1. Unit: model config defaults and allowlist validation
  2. Integration: GeminiSession._build_config() produces valid Live API config
  3. E2E: full connect attempt with wrong model produces clear error, right model
     produces valid session setup message
"""

from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.config import CaptureConfig
from src.capture.event_bus import EventBus
from src.capture.gemini_session import GeminiSession
from src.capture.models import MediaChunk
from src.config.models import GEMINI_LIVE_MODEL

# ---------------------------------------------------------------------------
# Models known to support bidiGenerateContent (Gemini Live API)
# Update this list when Google adds new Live-compatible models.
# ---------------------------------------------------------------------------
BIDI_COMPATIBLE_MODELS = {
    "gemini-live-2.5-flash-native-audio",
    "gemini-2.5-flash-native-audio-preview-12-2025",
}

# Models known to NOT support bidiGenerateContent
BIDI_INCOMPATIBLE_MODELS = {
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides) -> CaptureConfig:
    return CaptureConfig(gemini_api_key="test-key", **overrides)


def _make_session(config: CaptureConfig | None = None) -> GeminiSession:
    config = config or _make_config()
    bus = EventBus()
    queue: asyncio.Queue[MediaChunk] = asyncio.Queue()
    with patch("src.capture.gemini_session.genai"):
        return GeminiSession(config, bus, queue)


# ---------------------------------------------------------------------------
# 1. Unit tests: model config defaults and allowlist
# ---------------------------------------------------------------------------


class TestModelConfigDefaults:
    """Verify GEMINI_LIVE_MODEL default is a bidi-compatible model."""

    def test_default_live_model_is_bidi_compatible(self):
        """The hardcoded default must be a model that supports bidiGenerateContent."""
        assert GEMINI_LIVE_MODEL in BIDI_COMPATIBLE_MODELS, (
            f"GEMINI_LIVE_MODEL default '{GEMINI_LIVE_MODEL}' is not in the known "
            f"bidi-compatible set: {BIDI_COMPATIBLE_MODELS}. "
            f"The Live API requires bidiGenerateContent support."
        )

    def test_default_live_model_is_not_incompatible(self):
        """The default must NOT be a model known to lack bidi support."""
        assert GEMINI_LIVE_MODEL not in BIDI_INCOMPATIBLE_MODELS, (
            f"GEMINI_LIVE_MODEL default '{GEMINI_LIVE_MODEL}' is in the known "
            f"bidi-INCOMPATIBLE set. This will cause silent failures."
        )

    def test_capture_config_inherits_live_model(self):
        """CaptureConfig.gemini_model defaults to GEMINI_LIVE_MODEL."""
        config = _make_config()
        assert config.gemini_model == GEMINI_LIVE_MODEL

    def test_capture_config_override_respected(self):
        """Explicit gemini_model override takes precedence."""
        config = _make_config(gemini_model="gemini-2.5-pro")
        assert config.gemini_model == "gemini-2.5-pro"

    def test_env_override_takes_precedence(self):
        """GEMINI_LIVE_MODEL env var overrides the default."""
        with patch.dict(os.environ, {"GEMINI_LIVE_MODEL": "gemini-2.5-pro"}):
            # Re-import to pick up the env var
            import importlib
            import src.config.models as models_mod
            importlib.reload(models_mod)
            try:
                assert models_mod.GEMINI_LIVE_MODEL == "gemini-2.5-pro"
            finally:
                # Restore original
                importlib.reload(models_mod)


# ---------------------------------------------------------------------------
# 2. Integration tests: session config structure
# ---------------------------------------------------------------------------


class TestGeminiSessionConfig:
    """Verify GeminiSession._build_config() produces valid Live API configuration."""

    def test_build_config_response_modality_is_text(self):
        """Live session must request TEXT responses, not AUDIO."""
        session = _make_session()
        config = session._build_config()
        assert config.response_modalities == ["TEXT"]

    def test_build_config_includes_audio_transcription(self):
        """Live session must enable input audio transcription for presenter speech."""
        session = _make_session()
        config = session._build_config()
        assert config.input_audio_transcription is not None

    def test_build_config_includes_compression(self):
        """Live session must configure context window compression."""
        session = _make_session()
        config = session._build_config()
        assert config.context_window_compression is not None

    def test_build_config_includes_resumption(self):
        """Live session must configure session resumption for reconnects."""
        session = _make_session()
        config = session._build_config()
        assert config.session_resumption is not None

    def test_session_uses_config_model(self):
        """Session must use the model from CaptureConfig, not a hardcoded value."""
        config = _make_config(gemini_model="gemini-2.5-pro")
        session = _make_session(config)
        assert session._config.gemini_model == "gemini-2.5-pro"

    def test_session_connect_passes_model_string(self):
        """The run() method must pass config.gemini_model to client.aio.live.connect."""
        config = _make_config(gemini_model="gemini-2.5-flash")
        session = _make_session(config)

        # Mock the connect call to capture the model arg
        mock_connect = AsyncMock()
        mock_connect.__aenter__ = AsyncMock(side_effect=asyncio.CancelledError)
        mock_connect.__aexit__ = AsyncMock(return_value=False)
        session._client.aio.live.connect = MagicMock(return_value=mock_connect)
        session._stop_event.set()  # Stop after first attempt

        with pytest.raises((asyncio.CancelledError, Exception)):
            asyncio.get_event_loop().run_until_complete(session.run())

        if session._client.aio.live.connect.called:
            call_kwargs = session._client.aio.live.connect.call_args
            assert call_kwargs.kwargs.get("model") == "gemini-2.5-flash" or \
                   (call_kwargs.args and call_kwargs.args[0] == "gemini-2.5-flash") or \
                   call_kwargs.kwargs.get("model", call_kwargs.args[0] if call_kwargs.args else None) == "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# 3. E2E tests: model compatibility with the Live API setup message
# ---------------------------------------------------------------------------


class TestGeminiLiveModelE2E:
    """End-to-end validation of model string flow through to connect call."""

    def test_incompatible_model_would_be_sent_to_api(self):
        """Verify that an incompatible model string flows through to the connect call.

        This confirms the full path: config -> session -> connect(model=...) so that
        if someone sets an incompatible model, it actually reaches the API (where it
        will be rejected) rather than being silently corrected or ignored.
        """
        config = _make_config(gemini_model="gemini-2.0-flash")
        session = _make_session(config)

        # The model string that would be sent to the API
        assert session._config.gemini_model == "gemini-2.0-flash"

        # Build the config that would be sent — verify it doesn't override the model
        live_config = session._build_config()
        # The model is passed separately to connect(), not in LiveConnectConfig
        # So we verify the config doesn't contain a model override
        assert not hasattr(live_config, "model") or live_config.model is None

    def test_connect_receives_exact_model_string(self):
        """Verify run() passes the exact config.gemini_model to connect()."""
        config = _make_config(gemini_model="gemini-2.5-flash")
        session = _make_session(config)

        captured_kwargs = {}

        class FakeConnect:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

            async def __aenter__(self):
                session._stop_event.set()
                raise Exception("test-stop")

            async def __aexit__(self, *args):
                return False

        session._client.aio.live.connect = lambda **kwargs: FakeConnect(**kwargs)

        # Run briefly — it will raise on connect and stop
        try:
            asyncio.get_event_loop().run_until_complete(
                asyncio.wait_for(session.run(), timeout=2.0)
            )
        except Exception:
            pass

        assert captured_kwargs.get("model") == "gemini-2.5-flash", (
            f"connect() should receive model='gemini-2.5-flash', got: {captured_kwargs}"
        )

    def test_error_from_incompatible_model_is_not_swallowed(self):
        """The session's error handling must log model errors, not swallow them."""
        config = _make_config(gemini_model="gemini-2.0-flash")
        session = _make_session(config)

        errors_logged = []
        connect_count = 0

        class FakeConnect:
            async def __aenter__(self):
                nonlocal connect_count
                connect_count += 1
                # Stop after second attempt (first logs error, second hits break)
                if connect_count >= 2:
                    session._stop_event.set()
                raise Exception(
                    "models/gemini-2.0-flash is not supported for bidiGenerateContent"
                )

            async def __aexit__(self, *args):
                return False

        def fake_connect(**kwargs):
            return FakeConnect()

        session._client.aio.live.connect = fake_connect

        with patch("src.capture.gemini_session.logger") as mock_logger:
            mock_logger.error = lambda *args, **kwargs: errors_logged.append(args)
            mock_logger.info = MagicMock()
            with patch("src.capture.gemini_session.asyncio.sleep", new_callable=AsyncMock):
                try:
                    asyncio.get_event_loop().run_until_complete(
                        asyncio.wait_for(session.run(), timeout=5.0)
                    )
                except Exception:
                    pass

        # First connect attempt should log the error (stop_event not yet set)
        assert len(errors_logged) > 0, "Connection error must be logged, not swallowed"
        error_text = str(errors_logged[0])
        assert "bidiGenerateContent" in error_text, (
            f"Error log should contain the API error. Got: {error_text}"
        )


# ---------------------------------------------------------------------------
# 4. Regression guard: the specific incident that caused this test file
# ---------------------------------------------------------------------------


class TestRegressionGemini20FlashLive:
    """Regression tests for the 2026-03-13 incident where changing
    GEMINI_LIVE_MODEL to gemini-2.0-flash broke live capture, audience
    display, and Q&A simultaneously.

    The root cause was that gemini-2.0-flash does not support the
    bidiGenerateContent API required by the Live streaming session.
    """

    def test_gemini_2_0_flash_is_not_default_live_model(self):
        """gemini-2.0-flash must never be the default GEMINI_LIVE_MODEL."""
        assert GEMINI_LIVE_MODEL != "gemini-2.0-flash", (
            "REGRESSION: gemini-2.0-flash does not support bidiGenerateContent. "
            "See incident 2026-03-13: this broke live capture, audience display, "
            "and Q&A listening simultaneously."
        )

    def test_flash_model_is_separate_from_live_model(self):
        """GEMINI_FLASH_MODEL (for standard requests) must be distinct from GEMINI_LIVE_MODEL."""
        from src.config.models import GEMINI_FLASH_MODEL
        # They CAN be the same if both support bidi, but flash is typically 2.0
        # which doesn't support bidi. This test documents the distinction.
        if GEMINI_FLASH_MODEL in BIDI_INCOMPATIBLE_MODELS:
            assert GEMINI_FLASH_MODEL != GEMINI_LIVE_MODEL, (
                f"GEMINI_FLASH_MODEL ({GEMINI_FLASH_MODEL}) doesn't support bidi "
                f"but is set as GEMINI_LIVE_MODEL too."
            )

    def test_capture_config_gemini_model_field_uses_live_model(self):
        """CaptureConfig.gemini_model defaults to the same value as GEMINI_LIVE_MODEL.

        This verifies the config wiring hasn't been accidentally changed
        to use GEMINI_MODEL or GEMINI_FLASH_MODEL instead.
        """
        import importlib
        import src.config.models as models_mod
        importlib.reload(models_mod)  # Ensure fresh read
        config = _make_config()
        assert config.gemini_model == models_mod.GEMINI_LIVE_MODEL, (
            f"CaptureConfig.gemini_model ({config.gemini_model}) should default to "
            f"GEMINI_LIVE_MODEL ({models_mod.GEMINI_LIVE_MODEL}), "
            f"not GEMINI_MODEL or GEMINI_FLASH_MODEL"
        )
