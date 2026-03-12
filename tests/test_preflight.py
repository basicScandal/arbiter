"""Tests for pre-flight hardware checks before demo start."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.capture.config import CaptureConfig
from src.capture.preflight import PreflightResult, run_preflight


def _make_config(**overrides) -> CaptureConfig:
    defaults = {"gemini_api_key": "test-key", "camera_device_index": 0}
    defaults.update(overrides)
    return CaptureConfig(**defaults)


class TestPreflightResult:
    def test_default_ok(self):
        r = PreflightResult()
        assert r.ok is True
        assert r.errors == []
        assert r.warnings == []

    def test_fail_sets_ok_false(self):
        r = PreflightResult()
        r.fail("camera broken")
        assert r.ok is False
        assert "camera broken" in r.errors

    def test_warn_keeps_ok_true(self):
        r = PreflightResult()
        r.warn("audio flaky")
        assert r.ok is True
        assert "audio flaky" in r.warnings

    def test_summary_all_pass(self):
        r = PreflightResult()
        assert "passed" in r.summary.lower()

    def test_summary_with_errors(self):
        r = PreflightResult()
        r.fail("no camera")
        assert "FAIL" in r.summary
        assert "no camera" in r.summary

    def test_summary_with_warnings(self):
        r = PreflightResult()
        r.warn("audio default device")
        assert "WARN" in r.summary


class TestRunPreflight:
    @pytest.mark.asyncio
    async def test_camera_pass_audio_pass(self):
        """All checks pass when hardware is available."""
        config = _make_config()

        with (
            patch("src.capture.preflight._check_camera", return_value=(True, "Camera OK (1920x1080)")),
            patch("src.capture.preflight._check_audio", return_value=(True, "Audio OK (default)")),
        ):
            result = await run_preflight(config)

        assert result.ok is True
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_camera_fail_blocks_start(self):
        """Camera failure results in a failed preflight."""
        config = _make_config()

        with (
            patch("src.capture.preflight._check_camera", return_value=(False, "Cannot open camera device 0")),
            patch("src.capture.preflight._check_audio", return_value=(True, "Audio OK")),
        ):
            result = await run_preflight(config)

        assert result.ok is False
        assert any("camera" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_audio_fail_is_warning_not_blocker(self):
        """Audio failure is a warning, not a blocker — demo can proceed without mic."""
        config = _make_config()

        with (
            patch("src.capture.preflight._check_camera", return_value=(True, "Camera OK")),
            patch("src.capture.preflight._check_audio", return_value=(False, "No audio device")),
        ):
            result = await run_preflight(config)

        assert result.ok is True
        assert any("audio" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_missing_gemini_key_fails(self):
        """Missing Gemini API key fails preflight."""
        config = _make_config(gemini_api_key="")

        with (
            patch("src.capture.preflight._check_camera", return_value=(True, "Camera OK")),
            patch("src.capture.preflight._check_audio", return_value=(True, "Audio OK")),
        ):
            result = await run_preflight(config)

        assert result.ok is False
        assert any("gemini" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_camera_exception_handled(self):
        """Camera check that throws an exception is caught and reported."""
        config = _make_config()

        with (
            patch("src.capture.preflight._check_camera", side_effect=RuntimeError("segfault")),
            patch("src.capture.preflight._check_audio", return_value=(True, "Audio OK")),
        ):
            result = await run_preflight(config)

        assert result.ok is False
        assert any("crashed" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_audio_exception_is_warning(self):
        """Audio check that throws is a warning, not a failure."""
        config = _make_config()

        with (
            patch("src.capture.preflight._check_camera", return_value=(True, "Camera OK")),
            patch("src.capture.preflight._check_audio", side_effect=OSError("device busy")),
        ):
            result = await run_preflight(config)

        assert result.ok is True
        assert any("crashed" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_all_failures(self):
        """Multiple failures all reported."""
        config = _make_config(gemini_api_key="")

        with (
            patch("src.capture.preflight._check_camera", return_value=(False, "No camera")),
            patch("src.capture.preflight._check_audio", return_value=(False, "No audio")),
        ):
            result = await run_preflight(config)

        assert result.ok is False
        assert len(result.errors) == 2  # camera + gemini key
        assert len(result.warnings) == 1  # audio


class TestPreflightInStartCommand:
    """Test that the WebOperator start command runs preflight and blocks on failure."""

    @pytest.mark.asyncio
    async def test_start_blocked_by_preflight_failure(self):
        """Start command returns failure when preflight camera check fails."""
        from unittest.mock import AsyncMock

        from src.capture.demo_machine import DemoMachine
        from src.capture.event_bus import EventBus
        from src.commentary.display_server import DisplayServer
        from src.operator.web import WebOperator

        dm = DemoMachine(event_bus=EventBus())
        ds = MagicMock(spec=DisplayServer)
        ds.app = MagicMock()
        config = _make_config()

        operator = WebOperator(
            demo_machine=dm,
            event_bus=EventBus(),
            display_server=ds,
            capture_config=config,
        )

        ws = AsyncMock()
        data = {"action": "start", "team_name": "Oscar", "track": "ROGUE::AGENT"}

        with patch("src.operator.web.run_preflight") as mock_pf:
            failed_result = PreflightResult()
            failed_result.fail("Cannot open camera device 0")
            mock_pf.return_value = failed_result

            await operator._handle_command(data, ws)

        # Should have sent failure result, NOT started the demo
        ws.send_json.assert_called()
        call_args = ws.send_json.call_args[0][0]
        assert call_args["success"] is False
        assert "pre-flight" in call_args["message"].lower()
        assert dm.current_state.id == "idle"

    @pytest.mark.asyncio
    async def test_start_proceeds_after_preflight_pass(self):
        """Start command proceeds normally when preflight passes."""
        from unittest.mock import AsyncMock

        from src.capture.demo_machine import DemoMachine
        from src.capture.event_bus import EventBus
        from src.commentary.display_server import DisplayServer
        from src.operator.web import WebOperator

        dm = DemoMachine(event_bus=EventBus())
        ds = MagicMock(spec=DisplayServer)
        ds.app = MagicMock()
        ds.clear = AsyncMock()
        ds.push_capture_started = AsyncMock()
        config = _make_config()

        operator = WebOperator(
            demo_machine=dm,
            event_bus=EventBus(),
            display_server=ds,
            capture_config=config,
        )

        ws = AsyncMock()
        data = {"action": "start", "team_name": "Oscar", "track": "ROGUE::AGENT"}

        with patch("src.operator.web.run_preflight") as mock_pf:
            mock_pf.return_value = PreflightResult()  # all ok

            await operator._handle_command(data, ws)

        # Demo should have started
        assert dm.current_state.id == "capturing"
