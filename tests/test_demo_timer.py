"""Tests for the per-demo timeout and warning system."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from src.capture.demo_machine import DemoMachine
from src.capture.event_bus import EventBus
from src.capture.models import DemoSession
from src.commentary.display_server import DisplayServer
from src.operator.web import MAX_DEMO_DURATION, WebOperator, _WARNING_RATIO


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
# Config
# ---------------------------------------------------------------------------


class TestTimerConfig:
    def test_default_max_duration(self):
        assert MAX_DEMO_DURATION == 600.0

    def test_warning_ratio(self):
        assert _WARNING_RATIO == 0.9


# ---------------------------------------------------------------------------
# Timer lifecycle
# ---------------------------------------------------------------------------


class TestDemoTimer:
    @pytest.mark.asyncio
    async def test_start_creates_task(self, web_operator: WebOperator):
        web_operator._start_demo_timer()
        assert web_operator._demo_timer_task is not None
        assert not web_operator._demo_timer_task.done()
        web_operator._cancel_demo_timer()

    @pytest.mark.asyncio
    async def test_cancel_clears_task(self, web_operator: WebOperator):
        web_operator._start_demo_timer()
        web_operator._cancel_demo_timer()
        assert web_operator._demo_timer_task is None

    @pytest.mark.asyncio
    async def test_cancel_is_idempotent(self, web_operator: WebOperator):
        """Cancelling with no active timer should not raise."""
        web_operator._cancel_demo_timer()
        web_operator._cancel_demo_timer()

    @pytest.mark.asyncio
    async def test_start_cancels_existing_timer(self, web_operator: WebOperator):
        """Starting a new timer cancels any existing one."""
        web_operator._start_demo_timer()
        first_task = web_operator._demo_timer_task
        web_operator._start_demo_timer()
        await asyncio.sleep(0)
        assert first_task.cancelled()
        web_operator._cancel_demo_timer()


# ---------------------------------------------------------------------------
# Timer loop behavior (using a fast-running patched loop)
# ---------------------------------------------------------------------------


class TestDemoTimerLoop:
    """Test _demo_timer_loop by calling it directly with pre-set session times.

    Instead of patching asyncio.sleep (which breaks the test harness), we
    use a wrapper that calls the loop once with the sleep reduced to 0.
    """

    @staticmethod
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

    @pytest.mark.asyncio
    async def test_timer_sends_warning_at_threshold(self, web_operator: WebOperator):
        """Timer broadcasts warning when elapsed reaches 90% of max."""
        elapsed = MAX_DEMO_DURATION * 0.91
        session = DemoSession(team_name="T", started_at=time.time() - elapsed)
        web_operator._demo_machine.current_session = session

        messages = []

        async def capture_broadcast(msg):
            messages.append(msg)

        web_operator._broadcast_to_operators = capture_broadcast

        await self._run_loop_once(web_operator)

        warnings = [m for m in messages if m.get("type") == "demo_timer" and m.get("level") == "warning"]
        assert len(warnings) >= 1
        assert "remaining" in warnings[0]["message"]

    @pytest.mark.asyncio
    async def test_timer_sends_critical_at_max(self, web_operator: WebOperator):
        """Timer broadcasts critical alert when elapsed exceeds max."""
        elapsed = MAX_DEMO_DURATION + 10
        session = DemoSession(team_name="T", started_at=time.time() - elapsed)
        web_operator._demo_machine.current_session = session

        messages = []

        async def capture_broadcast(msg):
            messages.append(msg)

        web_operator._broadcast_to_operators = capture_broadcast

        await self._run_loop_once(web_operator)

        criticals = [m for m in messages if m.get("type") == "demo_timer" and m.get("level") == "critical"]
        assert len(criticals) >= 1
        assert "exceeded" in criticals[0]["message"]

    @pytest.mark.asyncio
    async def test_timer_exits_when_no_session(self, web_operator: WebOperator):
        """Timer exits gracefully if session is cleared."""
        web_operator._demo_machine.current_session = None
        await self._run_loop_once(web_operator)
        # If we get here, it exited cleanly

    @pytest.mark.asyncio
    async def test_timer_message_includes_elapsed_and_max(self, web_operator: WebOperator):
        """Timer messages include elapsed time and max duration."""
        session = DemoSession(team_name="T", started_at=time.time() - (MAX_DEMO_DURATION + 10))
        web_operator._demo_machine.current_session = session

        messages = []

        async def capture_broadcast(msg):
            messages.append(msg)

        web_operator._broadcast_to_operators = capture_broadcast

        await self._run_loop_once(web_operator)

        timer_msgs = [m for m in messages if m.get("type") == "demo_timer"]
        assert len(timer_msgs) >= 1
        assert "elapsed" in timer_msgs[0]
        assert "max_duration" in timer_msgs[0]
        assert timer_msgs[0]["max_duration"] == MAX_DEMO_DURATION

    @pytest.mark.asyncio
    async def test_no_warning_before_threshold(self, web_operator: WebOperator):
        """No warning when demo is well within time limit."""
        session = DemoSession(team_name="T", started_at=time.time() - 60)  # 1 minute into 10-min demo
        web_operator._demo_machine.current_session = session

        messages = []

        async def capture_broadcast(msg):
            messages.append(msg)

        web_operator._broadcast_to_operators = capture_broadcast

        await self._run_loop_once(web_operator)

        timer_msgs = [m for m in messages if m.get("type") == "demo_timer"]
        assert len(timer_msgs) == 0
