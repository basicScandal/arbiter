"""Tests for demo timer auto-stop behavior after overtime.

Verifies that _demo_timer_loop calls _demo_machine.send("stop_demo")
when a demo exceeds MAX_DEMO_DURATION, preventing capture from running
indefinitely and leaking stale media into the next team's queue.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.capture.demo_machine import DemoMachine
from src.capture.event_bus import EventBus
from src.capture.models import DemoSession
from src.commentary.display_server import DisplayServer
from src.operator.web import MAX_DEMO_DURATION, WebOperator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def web_operator(event_bus: EventBus) -> WebOperator:
    machine = DemoMachine(event_bus=event_bus)
    display = MagicMock(spec=DisplayServer)
    display.app = MagicMock()
    op = WebOperator(
        demo_machine=machine,
        event_bus=event_bus,
        display_server=display,
    )
    return op


# ---------------------------------------------------------------------------
# Helper: run the timer loop with near-zero sleep
# ---------------------------------------------------------------------------


async def _run_loop_once(web_operator: WebOperator) -> None:
    """Run the timer loop with near-zero sleep, cancelling after one iteration."""
    import src.operator.web as web_mod

    original_sleep = asyncio.sleep
    call_count = 0

    async def _fast_sleep(duration):
        nonlocal call_count
        call_count += 1
        if call_count > 1:
            raise asyncio.CancelledError
        await original_sleep(0)

    old = web_mod.asyncio.sleep
    web_mod.asyncio.sleep = _fast_sleep
    try:
        await web_operator._demo_timer_loop()
    except asyncio.CancelledError:
        pass
    finally:
        web_mod.asyncio.sleep = old


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDemoTimerAutoStop:
    """Verify that exceeding MAX_DEMO_DURATION triggers an automatic stop."""

    @pytest.mark.asyncio
    async def test_autostop_calls_stop_demo(self, web_operator: WebOperator):
        """After overtime, the timer must call _demo_machine.send('stop_demo')."""
        # Put machine into capturing state
        web_operator._demo_machine.send("start_demo", team_name="OverTimeTeam")

        # Backdate session to exceed max duration
        session = web_operator._demo_machine.current_session
        session.started_at = time.time() - (MAX_DEMO_DURATION + 10)

        # Capture broadcasts (we don't care about their content here)
        web_operator._broadcast_to_operators = AsyncMock(return_value=None)

        await _run_loop_once(web_operator)

        # Machine should have transitioned to stopped
        assert web_operator._demo_machine.current_state.id == "stopped"

    @pytest.mark.asyncio
    async def test_autostop_sends_critical_before_stopping(self, web_operator: WebOperator):
        """The critical alert must be broadcast before the auto-stop."""
        web_operator._demo_machine.send("start_demo", team_name="AlertTeam")
        session = web_operator._demo_machine.current_session
        session.started_at = time.time() - (MAX_DEMO_DURATION + 5)

        messages = []

        async def capture_broadcast(msg):
            messages.append(msg)

        web_operator._broadcast_to_operators = capture_broadcast

        await _run_loop_once(web_operator)

        criticals = [
            m for m in messages
            if m.get("type") == "demo_timer" and m.get("level") == "critical"
        ]
        assert len(criticals) >= 1
        assert "exceeded" in criticals[0]["message"]
        # And the machine was stopped
        assert web_operator._demo_machine.current_state.id == "stopped"

    @pytest.mark.asyncio
    async def test_autostop_handles_already_stopped(self, web_operator: WebOperator):
        """If the machine is already stopped, the auto-stop should not raise."""
        # Start and then manually stop
        web_operator._demo_machine.send("start_demo", team_name="AlreadyStopped")
        web_operator._demo_machine.send("stop_demo")
        assert web_operator._demo_machine.current_state.id == "stopped"

        # Backdate session so it looks overtime
        session = web_operator._demo_machine.current_session
        session.started_at = time.time() - (MAX_DEMO_DURATION + 10)

        messages = []

        async def capture_broadcast(msg):
            messages.append(msg)

        web_operator._broadcast_to_operators = capture_broadcast

        # Should not raise even though stop_demo is not valid from stopped state
        await _run_loop_once(web_operator)

        # Machine stays in stopped (TransitionNotAllowed was caught)
        assert web_operator._demo_machine.current_state.id == "stopped"

    @pytest.mark.asyncio
    async def test_autostop_with_mocked_send(self, web_operator: WebOperator):
        """Directly verify send('stop_demo') is called using a mock."""
        web_operator._demo_machine.send("start_demo", team_name="MockTeam")
        session = web_operator._demo_machine.current_session
        session.started_at = time.time() - (MAX_DEMO_DURATION + 10)

        web_operator._broadcast_to_operators = AsyncMock(return_value=None)

        # Patch send to track calls while still forwarding to the real method
        original_send = web_operator._demo_machine.send
        send_calls = []

        def tracking_send(*args, **kwargs):
            send_calls.append(args)
            return original_send(*args, **kwargs)

        web_operator._demo_machine.send = tracking_send

        await _run_loop_once(web_operator)

        stop_calls = [c for c in send_calls if c[0] == "stop_demo"]
        assert len(stop_calls) == 1

    @pytest.mark.asyncio
    async def test_no_autostop_before_max_duration(self, web_operator: WebOperator):
        """Demo within time limit must NOT be auto-stopped."""
        web_operator._demo_machine.send("start_demo", team_name="OnTimeTeam")
        session = web_operator._demo_machine.current_session
        # Only 60 seconds into a 600-second demo
        session.started_at = time.time() - 60

        web_operator._broadcast_to_operators = AsyncMock(return_value=None)

        await _run_loop_once(web_operator)

        # Machine should still be capturing
        assert web_operator._demo_machine.current_state.id == "capturing"
