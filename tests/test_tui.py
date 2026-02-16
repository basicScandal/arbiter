"""Comprehensive test suite for the Arbiter TUI.

Tests widget composition, EventBus bridging, command handling, state
transitions, sidebar counters, defense panel, keyboard shortcuts,
LogRecord routing, and edge cases.

Uses Textual's headless test mode with asyncio.sleep() for sync
(pilot.pause() can hang when bus has active subscriptions).
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from statemachine.exceptions import TransitionNotAllowed

from src.capture.demo_machine import DemoMachine
from src.capture.event_bus import EventBus
from src.capture.models import (
    CaptureEvent,
    DemoStarted,
    DemoStopped,
    KeyFrameDetected,
    FrameData,
    TranscriptReceived,
    TranscriptSegment,
)
from src.defense.models import (
    InjectionAttempt,
    InjectionDetected,
    ObservationVerified,
    RoastGenerated,
    SanitizedOutput,
)
from src.operator.tui import ArbiterTUI
from src.operator.widgets import (
    ArbiterHeader,
    BusEvent,
    CommandInput,
    CommandSubmitted,
    DefensePanel,
    EventLog,
    LogRecord,
    StatusSidebar,
)
from textual.widgets import Footer, Input


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SLEEP = 0.15  # seconds for bus event propagation


def _make_app(bus: EventBus | None = None) -> ArbiterTUI:
    """Create an ArbiterTUI with a fresh bus and machine."""
    b = bus or EventBus()
    machine = DemoMachine(event_bus=b)
    return ArbiterTUI(demo_machine=machine, event_bus=b)


def _frame() -> FrameData:
    return FrameData(jpeg_data=b"\xff", width=1, height=1, timestamp=0.0)


def _attempt() -> InjectionAttempt:
    return InjectionAttempt(
        timestamp=0.0,
        injection_type="visual",
        content="ignore previous",
        pattern="instruction_override",
        confidence="high",
        team_name="TestTeam",
    )


# ---------------------------------------------------------------------------
# 1. Widget composition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_widgets_mount():
    """All six custom widgets plus Footer compose correctly."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        assert app.query_one(ArbiterHeader)
        assert app.query_one(EventLog)
        assert app.query_one(StatusSidebar)
        assert app.query_one(DefensePanel)
        assert app.query_one(CommandInput)
        assert app.query_one(Footer)


# ---------------------------------------------------------------------------
# 2. EventBus -> BusEvent bridge
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bus_event_bridge():
    """CaptureEvent published on bus arrives as BusEvent in the app."""
    bus = EventBus()
    app = _make_app(bus)
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        bus.publish(DemoStarted(team_name="BridgeTeam"))
        await asyncio.sleep(SLEEP)
        header = app.query_one(ArbiterHeader)
        assert header.state == "CAPTURING"
        assert header.team_name == "BridgeTeam"


# ---------------------------------------------------------------------------
# 3. Full demo lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_lifecycle():
    """start -> events -> stop -> reset cycle works end-to-end."""
    bus = EventBus()
    app = _make_app(bus)
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        header = app.query_one(ArbiterHeader)
        sidebar = app.query_one(StatusSidebar)

        # Start
        app.post_message(CommandSubmitted(command="start", args="LifecycleTeam"))
        await asyncio.sleep(SLEEP)
        assert header.state == "CAPTURING"
        assert sidebar.state == "CAPTURING"
        assert app.demo_machine.current_state.id == "capturing"

        # Publish some events
        bus.publish(KeyFrameDetected(frame=_frame()))
        bus.publish(TranscriptReceived(segment=TranscriptSegment(text="hello", timestamp=0.0)))
        await asyncio.sleep(SLEEP)
        assert sidebar.frame_count == 1
        assert sidebar.transcript_count == 1

        # Stop
        app.post_message(CommandSubmitted(command="stop", args=""))
        await asyncio.sleep(SLEEP)
        assert header.state == "STOPPED"
        assert app.demo_machine.current_state.id == "stopped"

        # Reset
        app.post_message(CommandSubmitted(command="reset", args=""))
        await asyncio.sleep(SLEEP)
        assert header.state == "IDLE"
        assert sidebar.frame_count == 0
        assert app.demo_machine.current_state.id == "idle"


# ---------------------------------------------------------------------------
# 4. Command parsing — individual commands
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_command_start():
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="start", args="Alpha"))
        await asyncio.sleep(SLEEP)
        assert app.demo_machine.current_state.id == "capturing"
        assert app.demo_machine.current_session.team_name == "Alpha"


@pytest.mark.asyncio
async def test_command_stop():
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="start", args="Alpha"))
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="stop", args=""))
        await asyncio.sleep(SLEEP)
        assert app.demo_machine.current_state.id == "stopped"


@pytest.mark.asyncio
async def test_command_pause_resume():
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="start", args="Alpha"))
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="pause", args=""))
        await asyncio.sleep(SLEEP)
        assert app.demo_machine.current_state.id == "paused"
        assert app.query_one(ArbiterHeader).state == "PAUSED"

        app.post_message(CommandSubmitted(command="resume", args=""))
        await asyncio.sleep(SLEEP)
        assert app.demo_machine.current_state.id == "capturing"
        assert app.query_one(ArbiterHeader).state == "CAPTURING"


@pytest.mark.asyncio
async def test_command_qa_requires_stopped():
    """qa command only works in stopped state."""
    bus = EventBus()
    app = _make_app(bus)
    published: list[CaptureEvent] = []

    async def capture(e: CaptureEvent):
        published.append(e)

    bus.subscribe("qa_requested", capture)

    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        # qa from idle — should warn, not publish
        app.post_message(CommandSubmitted(command="qa", args=""))
        await asyncio.sleep(SLEEP)
        assert len(published) == 0

        # Move to stopped
        app.post_message(CommandSubmitted(command="start", args="QATeam"))
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="stop", args=""))
        await asyncio.sleep(SLEEP)

        # Now qa should work
        app.post_message(CommandSubmitted(command="qa", args=""))
        await asyncio.sleep(SLEEP)
        assert len(published) == 1
        assert published[0].event_type == "qa_requested"


@pytest.mark.asyncio
async def test_command_deliberate():
    """deliberate command publishes DeliberationRequested."""
    bus = EventBus()
    app = _make_app(bus)
    published: list[CaptureEvent] = []

    async def capture(e: CaptureEvent):
        published.append(e)

    bus.subscribe("deliberation_requested", capture)

    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="deliberate", args=""))
        await asyncio.sleep(SLEEP)
        assert len(published) == 1


@pytest.mark.asyncio
async def test_command_status():
    """status command writes state to event log without error."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="status", args=""))
        await asyncio.sleep(SLEEP)
        # No crash = pass; state is idle
        assert app.demo_machine.current_state.id == "idle"


@pytest.mark.asyncio
async def test_command_help():
    """help command writes help text without error."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="help", args=""))
        await asyncio.sleep(SLEEP)
        # No crash = pass


@pytest.mark.asyncio
async def test_command_quit():
    """quit command exits the app."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="quit", args=""))
        await asyncio.sleep(SLEEP)
        # App should have exited (no exception)


# ---------------------------------------------------------------------------
# 5. Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_not_allowed_stop_from_idle():
    """Stopping from idle shows error, doesn't crash."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="stop", args=""))
        await asyncio.sleep(SLEEP)
        assert app.demo_machine.current_state.id == "idle"


@pytest.mark.asyncio
async def test_transition_not_allowed_start_while_capturing():
    """Starting while already capturing shows error."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="start", args="A"))
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="start", args="B"))
        await asyncio.sleep(SLEEP)
        # Still capturing team A
        assert app.demo_machine.current_session.team_name == "A"


@pytest.mark.asyncio
async def test_unknown_command():
    """Unknown command shows error text, doesn't crash."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="foobar", args=""))
        await asyncio.sleep(SLEEP)


@pytest.mark.asyncio
async def test_start_missing_team_name():
    """start with no args shows usage hint, doesn't transition."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="start", args=""))
        await asyncio.sleep(SLEEP)
        assert app.demo_machine.current_state.id == "idle"


# ---------------------------------------------------------------------------
# 6. Sidebar counters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sidebar_counters():
    """Sidebar frame/transcript/attack counts increment from bus events."""
    bus = EventBus()
    app = _make_app(bus)
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        sidebar = app.query_one(StatusSidebar)

        bus.publish(KeyFrameDetected(frame=_frame()))
        bus.publish(KeyFrameDetected(frame=_frame()))
        await asyncio.sleep(SLEEP)
        assert sidebar.frame_count == 2

        bus.publish(TranscriptReceived(
            segment=TranscriptSegment(text="hi", timestamp=0.0)
        ))
        await asyncio.sleep(SLEEP)
        assert sidebar.transcript_count == 1

        bus.publish(InjectionDetected(attempt=_attempt()))
        await asyncio.sleep(SLEEP)
        assert sidebar.attack_count == 1


# ---------------------------------------------------------------------------
# 7. Defense panel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_defense_injection_count():
    """Defense panel injection_count increments from InjectionDetected."""
    bus = EventBus()
    app = _make_app(bus)
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        defense = app.query_one(DefensePanel)

        bus.publish(InjectionDetected(attempt=_attempt()))
        bus.publish(InjectionDetected(attempt=_attempt()))
        await asyncio.sleep(SLEEP)
        assert defense.injection_count == 2


@pytest.mark.asyncio
async def test_defense_clean_count():
    """Defense panel clean_count updates from ObservationVerified."""
    bus = EventBus()
    app = _make_app(bus)
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        defense = app.query_one(DefensePanel)

        output = SanitizedOutput(
            team_name="X",
            observations=["obs1", "obs2", "obs3"],
            transcripts=[],
            injection_attempts=[],
            demo_duration=10.0,
        )
        bus.publish(ObservationVerified(output=output))
        await asyncio.sleep(SLEEP)
        assert defense.clean_count == 3


@pytest.mark.asyncio
async def test_defense_last_roast():
    """Defense panel last_roast updates from RoastGenerated."""
    bus = EventBus()
    app = _make_app(bus)
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        defense = app.query_one(DefensePanel)

        bus.publish(RoastGenerated(roast="Nice try, hacker!", attempt=_attempt()))
        await asyncio.sleep(SLEEP)
        assert defense.last_roast == "Nice try, hacker!"


# ---------------------------------------------------------------------------
# 8. Header state transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_header_state_transitions():
    """Header cycles: IDLE -> CAPTURING -> PAUSED -> CAPTURING -> STOPPED."""
    bus = EventBus()
    app = _make_app(bus)
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        header = app.query_one(ArbiterHeader)

        assert header.state == "IDLE"

        app.post_message(CommandSubmitted(command="start", args="T"))
        await asyncio.sleep(SLEEP)
        assert header.state == "CAPTURING"

        app.post_message(CommandSubmitted(command="pause", args=""))
        await asyncio.sleep(SLEEP)
        assert header.state == "PAUSED"

        app.post_message(CommandSubmitted(command="resume", args=""))
        await asyncio.sleep(SLEEP)
        assert header.state == "CAPTURING"

        app.post_message(CommandSubmitted(command="stop", args=""))
        await asyncio.sleep(SLEEP)
        assert header.state == "STOPPED"


# ---------------------------------------------------------------------------
# 9. Sparkline event history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sparkline_increment():
    """increment_event_count tracks events per second for sparkline."""
    bus = EventBus()
    app = _make_app(bus)
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        sidebar = app.query_one(StatusSidebar)

        # Publish several events quickly
        for _ in range(5):
            bus.publish(KeyFrameDetected(frame=_frame()))
        await asyncio.sleep(SLEEP)

        # _current_second_count should have incremented
        assert sidebar._current_second_count >= 5


# ---------------------------------------------------------------------------
# 10. Keyboard shortcuts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shortcut_prefill_start():
    """Ctrl+S prefills command input with 'start '."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.action_prefill_start()
        await asyncio.sleep(SLEEP)
        inp = app.query_one("#cmd-input", Input)
        assert inp.value == "start "


@pytest.mark.asyncio
async def test_shortcut_stop():
    """Ctrl+X sends stop command."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="start", args="ShortcutTeam"))
        await asyncio.sleep(SLEEP)
        app.action_send_stop()
        await asyncio.sleep(SLEEP)
        assert app.demo_machine.current_state.id == "stopped"


@pytest.mark.asyncio
async def test_shortcut_pause_resume():
    """Ctrl+P pauses, Ctrl+O resumes."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="start", args="T"))
        await asyncio.sleep(SLEEP)

        app.action_send_pause()
        await asyncio.sleep(SLEEP)
        assert app.demo_machine.current_state.id == "paused"

        app.action_send_resume()
        await asyncio.sleep(SLEEP)
        assert app.demo_machine.current_state.id == "capturing"


@pytest.mark.asyncio
async def test_shortcut_reset():
    """Ctrl+R sends reset command."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="start", args="T"))
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="stop", args=""))
        await asyncio.sleep(SLEEP)
        app.action_send_reset()
        await asyncio.sleep(SLEEP)
        assert app.demo_machine.current_state.id == "idle"


# ---------------------------------------------------------------------------
# 11. LogRecord routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_record_routing():
    """LogRecord message is handled by on_log_record without crash."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(LogRecord("Test log line", "yellow"))
        await asyncio.sleep(SLEEP)
        # No exception = pass; log line was appended to EventLog


@pytest.mark.asyncio
async def test_tui_log_handler_installs():
    """_install_log_handler adds handler that posts LogRecord messages."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        # The TUI installs a handler on mount; verify root logger has it
        root = logging.getLogger()
        from src.operator.tui import _TUILogHandler
        has_tui_handler = any(isinstance(h, _TUILogHandler) for h in root.handlers)
        assert has_tui_handler


# ---------------------------------------------------------------------------
# 12. Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rapid_events():
    """Publishing many events rapidly doesn't crash the TUI."""
    bus = EventBus()
    app = _make_app(bus)
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        for i in range(20):
            bus.publish(KeyFrameDetected(frame=_frame()))
        await asyncio.sleep(SLEEP * 3)
        sidebar = app.query_one(StatusSidebar)
        assert sidebar.frame_count == 20


@pytest.mark.asyncio
async def test_bus_event_bubble_false():
    """BusEvent has bubble=False to prevent infinite dispatch."""
    ev = BusEvent(DemoStarted(team_name="X"))
    assert ev.bubble is False


@pytest.mark.asyncio
async def test_log_record_bubble_false():
    """LogRecord has bubble=False."""
    lr = LogRecord("text", "dim")
    assert lr.bubble is False


@pytest.mark.asyncio
async def test_reset_clears_all_counters():
    """Reset command zeros all sidebar and defense counters."""
    bus = EventBus()
    app = _make_app(bus)
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        # Start and accumulate counters
        app.post_message(CommandSubmitted(command="start", args="T"))
        await asyncio.sleep(SLEEP)
        bus.publish(KeyFrameDetected(frame=_frame()))
        bus.publish(InjectionDetected(attempt=_attempt()))
        bus.publish(RoastGenerated(roast="roast!", attempt=_attempt()))
        await asyncio.sleep(SLEEP)

        sidebar = app.query_one(StatusSidebar)
        defense = app.query_one(DefensePanel)
        assert sidebar.frame_count >= 1
        assert defense.injection_count >= 1

        # Stop then reset
        app.post_message(CommandSubmitted(command="stop", args=""))
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="reset", args=""))
        await asyncio.sleep(SLEEP)

        assert sidebar.frame_count == 0
        assert sidebar.transcript_count == 0
        assert sidebar.attack_count == 0
        assert defense.injection_count == 0
        assert defense.clean_count == 0
        assert defense.last_roast == ""


@pytest.mark.asyncio
async def test_command_exit_alias():
    """'exit' command works same as 'quit'."""
    app = _make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="exit", args=""))
        await asyncio.sleep(SLEEP)


@pytest.mark.asyncio
async def test_qa_without_bus():
    """qa command with no event bus shows warning, doesn't crash."""
    machine = DemoMachine()
    app = ArbiterTUI(demo_machine=machine, event_bus=None)
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="qa", args=""))
        await asyncio.sleep(SLEEP)


@pytest.mark.asyncio
async def test_deliberate_without_bus():
    """deliberate command with no event bus shows warning."""
    machine = DemoMachine()
    app = ArbiterTUI(demo_machine=machine, event_bus=None)
    async with app.run_test(size=(120, 36)) as pilot:
        await asyncio.sleep(SLEEP)
        app.post_message(CommandSubmitted(command="deliberate", args=""))
        await asyncio.sleep(SLEEP)


@pytest.mark.asyncio
async def test_state_hint_messages():
    """_get_state_hint returns helpful hints for invalid transitions."""
    assert ArbiterTUI._get_state_hint("stop", "idle") is not None
    assert ArbiterTUI._get_state_hint("start", "capturing") is not None
    assert ArbiterTUI._get_state_hint("start", "stopped") is not None
    assert ArbiterTUI._get_state_hint("pause", "paused") is not None
    assert ArbiterTUI._get_state_hint("resume", "capturing") is not None
    assert ArbiterTUI._get_state_hint("reset", "capturing") is not None
    # Non-existent combo returns None
    assert ArbiterTUI._get_state_hint("foobar", "idle") is None
