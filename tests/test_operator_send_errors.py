"""Tests for WebOperator._send_result error logging.

Verifies that send failures are logged at WARNING level instead of being
silently swallowed, and that failures do not crash the operator pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect

from src.capture.demo_machine import DemoMachine
from src.capture.event_bus import EventBus
from src.operator.web import WebOperator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeDisplayServer:
    """Minimal DisplayServer stand-in that exposes a real FastAPI app."""

    def __init__(self) -> None:
        from fastapi import FastAPI

        self._app = FastAPI()
        self.cleared: int = 0
        self.capture_started_calls: list[dict] = []
        self.intermission_calls: list[dict] = []
        self.injection_blocked_calls: list[dict] = []

    @property
    def app(self):
        return self._app

    async def clear(self) -> None:
        self.cleared += 1

    async def push_capture_started(self, team_name: str, track: str) -> None:
        self.capture_started_calls.append({"team_name": team_name, "track": track})

    async def push_intermission(self, leaderboard: list, total_injections: int) -> None:
        self.intermission_calls.append({"leaderboard": leaderboard, "total_injections": total_injections})

    async def push_injection_blocked(
        self, category: str, confidence: str, roast: str, team_name: str,
    ) -> None:
        self.injection_blocked_calls.append({
            "category": category, "confidence": confidence,
            "roast": roast, "team_name": team_name,
        })


class FakeScoringPipeline:
    def __init__(self) -> None:
        self._pending_tracks: dict[str, str] = {}

    def set_track(self, team_name: str, track: str) -> None:
        self._pending_tracks[team_name] = track

    def cancel_reveal(self) -> None:
        pass


def _make_operator() -> WebOperator:
    """Create a WebOperator with mocked dependencies."""
    bus = EventBus()
    machine = DemoMachine(event_bus=bus)
    ds = FakeDisplayServer()
    sc = FakeScoringPipeline()
    op = WebOperator(
        demo_machine=machine,
        event_bus=bus,
        display_server=ds,
        scoring_pipeline=sc,
    )
    return op


def _mock_ws(send_side_effect=None) -> MagicMock:
    """Create a mock WebSocket with configurable send_json behavior."""
    ws = MagicMock()
    ws.send_json = AsyncMock(side_effect=send_side_effect)
    return ws


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_result_success():
    """Successful send delivers the correct JSON payload."""
    op = _make_operator()
    ws = _mock_ws()

    await op._send_result(ws, True, "Demo started for TeamX")

    ws.send_json.assert_awaited_once()
    payload = ws.send_json.call_args[0][0]
    assert payload["type"] == "command_result"
    assert payload["success"] is True
    assert payload["message"] == "Demo started for TeamX"


@pytest.mark.asyncio
async def test_send_result_timeout_logged(caplog):
    """When send_json hangs, the timeout is caught and logged at WARNING."""

    async def _hang(_data):
        await asyncio.sleep(100)  # will be cancelled by timeout

    op = _make_operator()
    ws = _mock_ws(send_side_effect=_hang)

    with caplog.at_level(logging.WARNING, logger="src.operator.web"):
        # Patch the timeout inside _send_result to be tiny for test speed
        with patch("src.operator.web.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            await op._send_result(ws, True, "Demo started")

    assert any("Failed to send command result" in r.message for r in caplog.records)
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) >= 1


@pytest.mark.asyncio
async def test_send_result_disconnect_logged(caplog):
    """When the client disconnects, the error is logged at WARNING, not swallowed."""
    op = _make_operator()
    ws = _mock_ws(send_side_effect=WebSocketDisconnect())

    with caplog.at_level(logging.WARNING, logger="src.operator.web"):
        await op._send_result(ws, False, "Cannot 'start' in state 'idle'")

    assert any("Failed to send command result" in r.message for r in caplog.records)
    assert any("success=False" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_send_failure_does_not_crash_pipeline():
    """After a failed send, the operator remains functional for the next call."""
    op = _make_operator()

    # First call: broken WebSocket
    bad_ws = _mock_ws(send_side_effect=ConnectionError("broken pipe"))
    await op._send_result(bad_ws, False, "error")

    # Second call: healthy WebSocket — should work fine
    good_ws = _mock_ws()
    await op._send_result(good_ws, True, "Demo started for TeamY")

    good_ws.send_json.assert_awaited_once()
    payload = good_ws.send_json.call_args[0][0]
    assert payload["success"] is True
    assert payload["message"] == "Demo started for TeamY"
