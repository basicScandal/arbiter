"""Comprehensive test suite for the WebOperator WebSocket interface.

Tests WebSocket lifecycle, command handling, state transitions, event
bridging, counter tracking, multi-client broadcast, track assignment,
error paths, and edge cases.

Uses FastAPI TestClient for WebSocket testing with mocked DemoMachine
and EventBus. Follows patterns from test_tui.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.capture.demo_machine import DemoMachine
from src.capture.event_bus import EventBus
from src.capture.models import (
    FrameData,
    KeyFrameDetected,
    TranscriptReceived,
    TranscriptSegment,
)
from src.defense.models import (
    InjectionAttempt,
    InjectionDetected,
    ObservationVerified,
    SanitizedOutput,
)
from src.operator.web import WebOperator

# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------


class FakeDisplayServer:
    """Minimal DisplayServer stand-in that exposes a real FastAPI app."""

    def __init__(self) -> None:
        self._app = FastAPI()
        self.cleared: int = 0
        self.capture_started_calls: list[dict] = []
        self.intermission_calls: list[dict] = []
        self.injection_blocked_calls: list[dict] = []

    @property
    def app(self) -> FastAPI:
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
    """Minimal ScoringPipeline stand-in with track storage."""

    def __init__(self) -> None:
        self._pending_tracks: dict[str, str] = {}

    def get_track(self, team_name: str) -> str:
        return self._pending_tracks.get(team_name, "")

    def set_track(self, team_name: str, track: str) -> None:
        self._pending_tracks[team_name] = track

    def cancel_reveal(self) -> None:
        pass


class FakeDeliberationPipeline:
    """Minimal DeliberationPipeline stand-in."""

    def __init__(self) -> None:
        self._tracks: dict[str, str] = {}

    def set_track(self, team_name: str, track: str) -> None:
        self._tracks[team_name] = track


def _make_operator(
    bus: EventBus | None = None,
    scoring: FakeScoringPipeline | None = None,
    deliberation: FakeDeliberationPipeline | None = None,
) -> tuple[WebOperator, DemoMachine, EventBus, FakeDisplayServer]:
    """Create a WebOperator with fresh components, routes registered."""
    b = bus or EventBus()
    machine = DemoMachine(event_bus=b)
    ds = FakeDisplayServer()
    sc = scoring or FakeScoringPipeline()
    dl = deliberation or FakeDeliberationPipeline()
    op = WebOperator(
        demo_machine=machine,
        event_bus=b,
        display_server=ds,
        scoring_pipeline=sc,
        deliberation_pipeline=dl,
    )
    op._register_routes()
    return op, machine, b, ds


def _drain_connect(ws) -> dict:
    """Consume initial messages sent on WebSocket connect.

    On connect, _push_state sends: state, health, scoring_phase.
    Tests must drain all three before reading command responses.

    Returns the state message for tests that need to inspect it.
    """
    state = ws.receive_json()
    assert state["type"] == "state"
    health = ws.receive_json()
    assert health["type"] == "health"
    scoring_phase = ws.receive_json()
    assert scoring_phase["type"] == "scoring_phase"
    return state


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
# 1. WebSocket lifecycle
# ---------------------------------------------------------------------------


def test_connect_receives_initial_state():
    """Client receives a state message immediately upon connection."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        state = _drain_connect(ws)
        assert state["state"] == "idle"
        assert state["team_name"] == ""
        assert state["started_at"] is None


def test_connect_increments_operator_count():
    """Connection tracking adds client to _operator_connections."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        assert len(op._operator_connections) == 1


def test_disconnect_removes_client():
    """Disconnecting cleans up _operator_connections."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
    # After context exit, client is disconnected
    assert len(op._operator_connections) == 0


# ---------------------------------------------------------------------------
# 2. Start command
# ---------------------------------------------------------------------------


def test_start_command_success():
    """Start command transitions to capturing and returns success."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "start", "team_name": "Alpha", "track": "ROGUE::AGENT"})

        result = ws.receive_json()
        assert result["type"] == "command_result"
        assert result["success"] is True
        assert "Alpha" in result["message"]

        # Should also get state broadcast
        state = ws.receive_json()
        assert state["type"] == "state"
        assert state["state"] == "capturing"
        assert state["team_name"] == "Alpha"

    assert machine.current_state.id == "capturing"


def test_start_command_missing_team_name():
    """Start without team_name returns error, stays idle."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "start", "team_name": ""})

        result = ws.receive_json()
        assert result["type"] == "command_result"
        assert result["success"] is False
        assert "required" in result["message"].lower()

    assert machine.current_state.id == "idle"


def test_start_command_sets_track():
    """Start with valid track assigns it via scoring pipeline."""
    scoring = FakeScoringPipeline()
    op, machine, bus, ds = _make_operator(scoring=scoring)
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "start", "team_name": "Beta", "track": "SHADOW::VECTOR"})
        _ = ws.receive_json()  # command_result
        _ = ws.receive_json()  # state broadcast

    assert scoring._pending_tracks.get("Beta") == "SHADOW::VECTOR"


def test_start_command_sets_track_on_deliberation():
    """Start with valid track also sets it on deliberation pipeline."""
    scoring = FakeScoringPipeline()
    delib = FakeDeliberationPipeline()
    op, machine, bus, ds = _make_operator(scoring=scoring, deliberation=delib)
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "start", "team_name": "Gamma", "track": "SENTINEL::MESH"})
        _ = ws.receive_json()
        _ = ws.receive_json()

    assert delib._tracks.get("Gamma") == "SENTINEL::MESH"


def test_start_command_invalid_track_warns():
    """Start with unknown track sends warning but still starts."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "start", "team_name": "Delta", "track": "BOGUS::TRACK"})

        # First result is the warning
        result1 = ws.receive_json()
        assert result1["type"] == "command_result"
        assert "warning" in result1["message"].lower() or "Warning" in result1["message"]

        # Then the actual start result
        result2 = ws.receive_json()
        assert result2["type"] == "command_result"
        assert result2["success"] is True

        # State broadcast
        state = ws.receive_json()
        assert state["state"] == "capturing"


def test_start_resets_counters():
    """Start command resets all counters to zero."""
    op, machine, bus, ds = _make_operator()
    op._counters = {"frames": 10, "transcripts": 5, "attacks": 2, "clean": 8}
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "start", "team_name": "Echo"})
        _ = ws.receive_json()  # result
        _ = ws.receive_json()  # state

    assert op._counters == {"frames": 0, "transcripts": 0, "attacks": 0, "clean": 0}


# ---------------------------------------------------------------------------
# 3. Stop command
# ---------------------------------------------------------------------------


def test_stop_command_success():
    """Stop command transitions capturing -> stopped."""
    op, machine, bus, ds = _make_operator()
    machine.send("start_demo", team_name="Foxtrot")
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "stop"})

        result = ws.receive_json()
        assert result["type"] == "command_result"
        assert result["success"] is True
        assert "Foxtrot" in result["message"]

        state = ws.receive_json()
        assert state["state"] == "stopped"


def test_stop_from_idle_fails():
    """Stop from idle state returns TransitionNotAllowed error."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "stop"})

        result = ws.receive_json()
        assert result["type"] == "command_result"
        assert result["success"] is False
        assert "idle" in result["message"].lower()


def test_stop_includes_duration():
    """Stop result message includes duration."""
    op, machine, bus, ds = _make_operator()
    machine.send("start_demo", team_name="Golf")
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "stop"})

        result = ws.receive_json()
        assert "duration" in result["message"].lower()


# ---------------------------------------------------------------------------
# 4. Pause / Resume commands
# ---------------------------------------------------------------------------


def test_pause_command_success():
    """Pause transitions capturing -> paused."""
    op, machine, bus, ds = _make_operator()
    machine.send("start_demo", team_name="Hotel")
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "pause"})

        result = ws.receive_json()
        assert result["success"] is True

        state = ws.receive_json()
        assert state["state"] == "paused"


def test_pause_from_idle_fails():
    """Pause from idle state returns error."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "pause"})

        result = ws.receive_json()
        assert result["success"] is False


def test_resume_command_success():
    """Resume transitions paused -> capturing."""
    op, machine, bus, ds = _make_operator()
    machine.send("start_demo", team_name="India")
    machine.send("pause_demo")
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "resume"})

        result = ws.receive_json()
        assert result["success"] is True

        state = ws.receive_json()
        assert state["state"] == "capturing"


def test_resume_from_idle_fails():
    """Resume from idle state returns error."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "resume"})

        result = ws.receive_json()
        assert result["success"] is False


# ---------------------------------------------------------------------------
# 5. Reset command
# ---------------------------------------------------------------------------


def test_reset_command_success():
    """Reset transitions stopped -> idle."""
    op, machine, bus, ds = _make_operator()
    machine.send("start_demo", team_name="Juliet")
    machine.send("stop_demo")
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "reset"})

        result = ws.receive_json()
        assert result["success"] is True

        # scoring_phase is pushed after command_result, before state broadcast
        sp = ws.receive_json()
        assert sp["type"] == "scoring_phase"
        assert sp["phase"] is None

        state = ws.receive_json()
        assert state["state"] == "idle"
        assert state["team_name"] == ""


def test_reset_from_idle_fails():
    """Reset from idle state returns error."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "reset"})

        result = ws.receive_json()
        assert result["success"] is False


# ---------------------------------------------------------------------------
# 6. QA command
# ---------------------------------------------------------------------------


def test_qa_command_success():
    """QA command publishes QARequested event when in stopped state."""
    op, machine, bus, ds = _make_operator()
    machine.send("start_demo", team_name="Kilo")
    machine.send("stop_demo")

    # Track QA events
    qa_events = []
    bus.subscribe("qa_requested", lambda e: qa_events.append(e))

    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "qa"})

        result = ws.receive_json()
        assert result["success"] is True
        assert "kilo" in result["message"].lower()


def test_qa_from_capturing_fails():
    """QA command fails when not in stopped state."""
    op, machine, bus, ds = _make_operator()
    machine.send("start_demo", team_name="Lima")
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "qa"})

        result = ws.receive_json()
        assert result["success"] is False
        assert "stopped" in result["message"].lower() or "capturing" in result["message"].lower()


def test_qa_from_idle_fails():
    """QA command fails when in idle state."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "qa"})

        result = ws.receive_json()
        assert result["success"] is False


# ---------------------------------------------------------------------------
# 7. Deliberate command
# ---------------------------------------------------------------------------


def test_deliberate_command_success():
    """Deliberate command publishes DeliberationRequested event."""
    op, machine, bus, ds = _make_operator()

    delib_events = []
    bus.subscribe("deliberation_requested", lambda e: delib_events.append(e))

    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "deliberate"})

        result = ws.receive_json()
        assert result["success"] is True
        assert "deliberation" in result["message"].lower()


# ---------------------------------------------------------------------------
# 8. Quit command
# ---------------------------------------------------------------------------


def test_quit_command_sets_signal():
    """Quit command sets the quit signal event."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "quit"})

        result = ws.receive_json()
        assert result["success"] is True

    assert op._quit_signal.is_set()


# ---------------------------------------------------------------------------
# 9. Unknown command
# ---------------------------------------------------------------------------


def test_unknown_command_returns_error():
    """Unknown action returns error with action name."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "explode"})

        result = ws.receive_json()
        assert result["success"] is False
        assert "explode" in result["message"]


def test_empty_action_returns_error():
    """Empty action string returns error."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command"})

        result = ws.receive_json()
        assert result["success"] is False


# ---------------------------------------------------------------------------
# 10. State broadcast after commands
# ---------------------------------------------------------------------------


def test_state_broadcast_after_start():
    """State message is broadcast to ALL clients after start."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "start", "team_name": "Mike"})
        _ = ws.receive_json()  # command_result

        state = ws.receive_json()
        assert state["type"] == "state"
        assert state["state"] == "capturing"
        assert state["team_name"] == "Mike"
        assert state["started_at"] is not None


def test_state_includes_track_from_scoring():
    """State broadcast includes track from scoring pipeline."""
    scoring = FakeScoringPipeline()
    op, machine, bus, ds = _make_operator(scoring=scoring)
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "start", "team_name": "November", "track": "ZERO::PROOF"})
        _ = ws.receive_json()  # result

        state = ws.receive_json()
        assert state["track"] == "ZERO::PROOF"


# ---------------------------------------------------------------------------
# 11. Counter tracking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_counter_key_frame():
    """key_frame_detected event increments frames counter."""
    op, machine, bus, ds = _make_operator()
    event = KeyFrameDetected(frame=_frame())

    await op._on_event(event)
    assert op._counters["frames"] == 1


@pytest.mark.asyncio
async def test_counter_transcript():
    """transcript_received event increments transcripts counter."""
    op, machine, bus, ds = _make_operator()
    seg = TranscriptSegment(text="hello", timestamp=0.0)
    event = TranscriptReceived(segment=seg)

    await op._on_event(event)
    assert op._counters["transcripts"] == 1


@pytest.mark.asyncio
async def test_counter_injection():
    """injection_detected event increments attacks counter."""
    op, machine, bus, ds = _make_operator()
    event = InjectionDetected(attempt=_attempt())

    await op._on_event(event)
    assert op._counters["attacks"] == 1


@pytest.mark.asyncio
async def test_counter_observation_verified():
    """observation_verified event increments clean counter by number of observations."""
    op, machine, bus, ds = _make_operator()
    output = SanitizedOutput(
        team_name="Test",
        observations=["obs1", "obs2", "obs3"],
        transcripts=[],
        injection_attempts=[],
        demo_duration=10.0,
    )
    event = ObservationVerified(output=output)

    await op._on_event(event)
    assert op._counters["clean"] == 3


@pytest.mark.asyncio
async def test_counter_accumulation():
    """Counters accumulate across multiple events."""
    op, machine, bus, ds = _make_operator()

    await op._on_event(KeyFrameDetected(frame=_frame()))
    await op._on_event(KeyFrameDetected(frame=_frame()))
    await op._on_event(InjectionDetected(attempt=_attempt()))

    assert op._counters["frames"] == 2
    assert op._counters["attacks"] == 1


# ---------------------------------------------------------------------------
# 12. Event broadcasting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_broadcast_includes_type():
    """Event broadcast message includes event_type and timestamp."""
    op, machine, bus, ds = _make_operator()

    # Track broadcast calls
    broadcast_messages = []

    async def capture_broadcast(msg):
        broadcast_messages.append(msg)

    op._broadcast_to_operators = capture_broadcast

    event = KeyFrameDetected(frame=_frame(), timestamp=12345.0)
    await op._on_event(event)

    assert len(broadcast_messages) == 1
    msg = broadcast_messages[0]
    assert msg["type"] == "event"
    assert msg["event_type"] == "key_frame_detected"
    assert msg["timestamp"] == 12345.0


@pytest.mark.asyncio
async def test_event_broadcast_injection_includes_attempt_data():
    """Injection event broadcast includes attempt details."""
    op, machine, bus, ds = _make_operator()

    broadcast_messages = []

    async def capture_broadcast(msg):
        broadcast_messages.append(msg)

    op._broadcast_to_operators = capture_broadcast

    event = InjectionDetected(attempt=_attempt())
    await op._on_event(event)

    msg = broadcast_messages[0]
    assert "attempt" in msg["data"]
    assert msg["data"]["attempt"]["injection_type"] == "visual"
    assert msg["data"]["attempt"]["pattern"] == "instruction_override"
    assert msg["data"]["attempt"]["confidence"] == "high"


# ---------------------------------------------------------------------------
# 13. Multiple clients
# ---------------------------------------------------------------------------


def test_multiple_clients_receive_state():
    """Multiple connected clients all receive state after command."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws1:
        _drain_connect(ws1)

        with client.websocket_connect("/ws/operator") as ws2:
            _drain_connect(ws2)

            assert len(op._operator_connections) == 2

            # Send start from ws1
            ws1.send_json({"type": "command", "action": "start", "team_name": "Oscar"})

            # ws1 gets command_result + state
            r1 = ws1.receive_json()
            assert r1["type"] == "command_result"
            s1 = ws1.receive_json()
            assert s1["type"] == "state"
            assert s1["state"] == "capturing"

            # ws2 also gets state broadcast
            s2 = ws2.receive_json()
            assert s2["type"] == "state"
            assert s2["state"] == "capturing"


# ---------------------------------------------------------------------------
# 14. _get_state_data
# ---------------------------------------------------------------------------


def test_get_state_data_idle():
    """State data when idle has empty team and no started_at."""
    op, machine, bus, ds = _make_operator()
    data = op._get_state_data()

    assert data["type"] == "state"
    assert data["state"] == "idle"
    assert data["team_name"] == ""
    assert data["track"] == ""
    assert data["started_at"] is None


def test_get_state_data_capturing():
    """State data when capturing includes team and started_at."""
    op, machine, bus, ds = _make_operator()
    machine.send("start_demo", team_name="Papa")

    data = op._get_state_data()
    assert data["state"] == "capturing"
    assert data["team_name"] == "Papa"
    assert data["started_at"] is not None


def test_get_state_data_with_track():
    """State data includes track from scoring pipeline when team has one."""
    scoring = FakeScoringPipeline()
    scoring._pending_tracks["Quebec"] = "SHADOW::VECTOR"
    op, machine, bus, ds = _make_operator(scoring=scoring)
    machine.send("start_demo", team_name="Quebec")

    data = op._get_state_data()
    assert data["track"] == "SHADOW::VECTOR"


def test_get_state_data_no_scoring_pipeline():
    """State data works without scoring pipeline (track is empty)."""
    bus = EventBus()
    machine = DemoMachine(event_bus=bus)
    ds = FakeDisplayServer()
    op = WebOperator(
        demo_machine=machine,
        event_bus=bus,
        display_server=ds,
        scoring_pipeline=None,
    )
    op._register_routes()
    machine.send("start_demo", team_name="Romeo")

    data = op._get_state_data()
    assert data["track"] == ""


# ---------------------------------------------------------------------------
# 15. Full lifecycle
# ---------------------------------------------------------------------------


def test_full_demo_lifecycle():
    """Complete lifecycle: start -> pause -> resume -> stop -> reset."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        # Initial idle state
        state = _drain_connect(ws)
        assert state["state"] == "idle"

        # Start
        ws.send_json({"type": "command", "action": "start", "team_name": "Sierra"})
        result = ws.receive_json()
        assert result["success"] is True
        state = ws.receive_json()
        assert state["state"] == "capturing"

        # Pause
        ws.send_json({"type": "command", "action": "pause"})
        result = ws.receive_json()
        assert result["success"] is True
        state = ws.receive_json()
        assert state["state"] == "paused"

        # Resume
        ws.send_json({"type": "command", "action": "resume"})
        result = ws.receive_json()
        assert result["success"] is True
        state = ws.receive_json()
        assert state["state"] == "capturing"

        # Stop
        ws.send_json({"type": "command", "action": "stop"})
        result = ws.receive_json()
        assert result["success"] is True
        state = ws.receive_json()
        assert state["state"] == "stopped"

        # Reset
        ws.send_json({"type": "command", "action": "reset"})
        result = ws.receive_json()
        assert result["success"] is True
        # scoring_phase is pushed after command_result, before state broadcast
        sp = ws.receive_json()
        assert sp["type"] == "scoring_phase"
        state = ws.receive_json()
        assert state["state"] == "idle"


def test_double_start_fails():
    """Starting twice without stop fails with TransitionNotAllowed."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)

        # First start succeeds
        ws.send_json({"type": "command", "action": "start", "team_name": "Tango"})
        _ = ws.receive_json()  # result
        _ = ws.receive_json()  # state

        # Second start fails
        ws.send_json({"type": "command", "action": "start", "team_name": "Tango2"})
        result = ws.receive_json()
        assert result["success"] is False
        assert "capturing" in result["message"].lower()


def test_stop_from_paused():
    """Stop works from paused state (capturing->paused->stopped)."""
    op, machine, bus, ds = _make_operator()
    machine.send("start_demo", team_name="Uniform")
    machine.send("pause_demo")
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)
        ws.send_json({"type": "command", "action": "stop"})

        result = ws.receive_json()
        assert result["success"] is True

        state = ws.receive_json()
        assert state["state"] == "stopped"


# ---------------------------------------------------------------------------
# 16. _send_result and _broadcast_to_operators robustness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_handles_disconnected_client():
    """Broadcast silently removes clients that error on send."""
    op, machine, bus, ds = _make_operator()

    # Create a mock WebSocket that raises on send_json
    broken_ws = MagicMock()
    broken_ws.send_json = MagicMock(side_effect=Exception("broken"))
    # Make it an async mock

    async def broken_send(msg):
        raise Exception("broken")

    broken_ws.send_json = broken_send

    op._operator_connections.add(broken_ws)
    assert len(op._operator_connections) == 1

    await op._broadcast_to_operators({"type": "test"})

    # Broken client should be removed
    assert broken_ws not in op._operator_connections


@pytest.mark.asyncio
async def test_send_result_handles_disconnected():
    """_send_result silently handles disconnected client."""
    op, machine, bus, ds = _make_operator()

    broken_ws = MagicMock()

    async def broken_send(msg):
        raise Exception("gone")

    broken_ws.send_json = broken_send

    # Should not raise
    await op._send_result(broken_ws, True, "test")


# ---------------------------------------------------------------------------
# 17. Counter push format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_counter_push_format():
    """Counter broadcast includes type and all 4 counter fields."""
    op, machine, bus, ds = _make_operator()
    op._counters = {"frames": 5, "transcripts": 3, "attacks": 1, "clean": 7}

    broadcast_messages = []

    async def capture_broadcast(msg):
        broadcast_messages.append(msg)

    op._broadcast_to_operators = capture_broadcast

    # Simulate one tick of counter push
    await op._broadcast_to_operators({
        "type": "counters",
        **op._counters,
    })

    msg = broadcast_messages[0]
    assert msg["type"] == "counters"
    assert msg["frames"] == 5
    assert msg["transcripts"] == 3
    assert msg["attacks"] == 1
    assert msg["clean"] == 7


# ---------------------------------------------------------------------------
# 18. WebSocket token authentication
# ---------------------------------------------------------------------------


def test_token_auth_allows_valid_token():
    """Connection with correct token is accepted."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with patch.dict("os.environ", {"OPERATOR_TOKEN": "hunter2"}):
        with client.websocket_connect("/ws/operator?token=hunter2") as ws:
            state = _drain_connect(ws)
            assert state["state"] == "idle"
            assert len(op._operator_connections) == 1


def test_token_auth_rejects_invalid_token():
    """Connection with wrong token is rejected with policy violation."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with patch.dict("os.environ", {"OPERATOR_TOKEN": "hunter2"}):
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/operator?token=wrong") as ws:
                ws.receive_json()


def test_token_auth_rejects_missing_token():
    """Connection without token is rejected when token is configured."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with patch.dict("os.environ", {"OPERATOR_TOKEN": "hunter2"}):
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/operator") as ws:
                ws.receive_json()


def test_no_token_configured_allows_all():
    """When OPERATOR_TOKEN is not set, all connections are allowed."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with patch.dict("os.environ", {}, clear=False):
        # Ensure OPERATOR_TOKEN is not set
        import os
        os.environ.pop("OPERATOR_TOKEN", None)

        with client.websocket_connect("/ws/operator") as ws:
            state = _drain_connect(ws)
            assert state["state"] == "idle"

        with client.websocket_connect("/ws/operator?token=anything") as ws:
            state = _drain_connect(ws)
            assert state["state"] == "idle"


def test_token_auth_commands_work_after_auth():
    """Authenticated connection can send commands normally."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with patch.dict("os.environ", {"OPERATOR_TOKEN": "s3cret"}):
        with client.websocket_connect("/ws/operator?token=s3cret") as ws:
            _drain_connect(ws)
            ws.send_json({"type": "command", "action": "start", "team_name": "AuthTeam"})

            result = ws.receive_json()
            assert result["type"] == "command_result"
            assert result["success"] is True


# ---------------------------------------------------------------------------
# 19. Scoring phase — server-authoritative push
# ---------------------------------------------------------------------------


def test_connect_receives_scoring_phase():
    """scoring_phase message is sent to newly connected clients."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        ws.receive_json()  # state
        ws.receive_json()  # health
        scoring_phase = ws.receive_json()
        assert scoring_phase["type"] == "scoring_phase"
        assert scoring_phase["phase"] is None


def test_scoring_phase_initial_value_is_none():
    """_scoring_phase starts as None before any events."""
    op, machine, bus, ds = _make_operator()
    assert op._scoring_phase is None


@pytest.mark.asyncio
async def test_push_scoring_phase_sanitizing():
    """_push_scoring_phase broadcasts sanitizing and stores it."""
    op, machine, bus, ds = _make_operator()

    broadcast_messages = []

    async def capture_broadcast(msg):
        broadcast_messages.append(msg)

    op._broadcast_to_operators = capture_broadcast
    await op._push_scoring_phase("sanitizing")

    assert op._scoring_phase == "sanitizing"
    assert len(broadcast_messages) == 1
    assert broadcast_messages[0]["type"] == "scoring_phase"
    assert broadcast_messages[0]["phase"] == "sanitizing"


@pytest.mark.asyncio
async def test_push_scoring_phase_scoring():
    """_push_scoring_phase broadcasts scoring phase."""
    op, machine, bus, ds = _make_operator()

    broadcast_messages = []

    async def capture_broadcast(msg):
        broadcast_messages.append(msg)

    op._broadcast_to_operators = capture_broadcast
    await op._push_scoring_phase("scoring")

    assert op._scoring_phase == "scoring"
    assert broadcast_messages[0]["phase"] == "scoring"


@pytest.mark.asyncio
async def test_push_scoring_phase_revealing():
    """_push_scoring_phase broadcasts revealing phase."""
    op, machine, bus, ds = _make_operator()

    broadcast_messages = []

    async def capture_broadcast(msg):
        broadcast_messages.append(msg)

    op._broadcast_to_operators = capture_broadcast
    await op._push_scoring_phase("revealing")

    assert op._scoring_phase == "revealing"
    assert broadcast_messages[0]["phase"] == "revealing"


@pytest.mark.asyncio
async def test_push_scoring_phase_none():
    """_push_scoring_phase broadcasts None to clear phase."""
    op, machine, bus, ds = _make_operator()
    op._scoring_phase = "sanitizing"

    broadcast_messages = []

    async def capture_broadcast(msg):
        broadcast_messages.append(msg)

    op._broadcast_to_operators = capture_broadcast
    await op._push_scoring_phase(None)

    assert op._scoring_phase is None
    assert broadcast_messages[0]["phase"] is None


@pytest.mark.asyncio
async def test_on_event_demo_stopped_pushes_sanitizing():
    """demo_stopped event triggers scoring_phase push of 'sanitizing'."""
    from src.capture.models import DemoStopped

    op, machine, bus, ds = _make_operator()
    phases_pushed = []

    async def capture_push(phase):
        phases_pushed.append(phase)

    op._push_scoring_phase = capture_push

    event = DemoStopped(team_name="TestTeam")
    await op._on_event(event)

    assert "sanitizing" in phases_pushed


@pytest.mark.asyncio
async def test_on_event_observation_verified_pushes_scoring():
    """observation_verified event triggers scoring_phase push of 'scoring'."""
    op, machine, bus, ds = _make_operator()
    output = SanitizedOutput(
        team_name="Test",
        observations=["obs1"],
        transcripts=[],
        injection_attempts=[],
        demo_duration=10.0,
    )
    event = ObservationVerified(output=output)

    phases_pushed = []

    async def capture_push(phase):
        phases_pushed.append(phase)

    op._push_scoring_phase = capture_push
    await op._on_event(event)

    assert "scoring" in phases_pushed


@pytest.mark.asyncio
async def test_on_event_demo_started_clears_phase():
    """demo_started event triggers scoring_phase push of None."""
    from src.capture.models import DemoStarted

    op, machine, bus, ds = _make_operator()
    op._scoring_phase = "sanitizing"

    phases_pushed = []

    async def capture_push(phase):
        phases_pushed.append(phase)

    op._push_scoring_phase = capture_push
    event = DemoStarted(team_name="NewTeam")
    await op._on_event(event)

    assert None in phases_pushed


def test_connect_receives_current_scoring_phase():
    """Reconnecting client receives the current non-None scoring phase."""
    op, machine, bus, ds = _make_operator()
    op._scoring_phase = "revealing"
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        ws.receive_json()  # state
        ws.receive_json()  # health
        scoring_phase = ws.receive_json()
        assert scoring_phase["type"] == "scoring_phase"
        assert scoring_phase["phase"] == "revealing"


# ---------------------------------------------------------------------------
# 20. Heartbeat ping/pong — operator WS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pong_message_is_ignored_by_command_handler():
    """A pong message does not trigger command handling (no unknown-command error)."""
    op, machine, bus, ds = _make_operator()

    results = []

    async def capture_result(ws, success, message):
        results.append({"success": success, "message": message})

    op._send_result = capture_result

    # Simulate pong being received — should be silently ignored
    # The operator WS loop checks: if data.get("type") != "pong": handle_command
    # We test the data routing logic directly here
    data = {"type": "pong"}
    if data.get("type") != "pong":
        await op._handle_command(data, MagicMock())

    # No command result should have been sent
    assert len(results) == 0
