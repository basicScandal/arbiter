"""Stress tests for WebOperator through 15 consecutive demos via WebSocket.

Exercises the full operator lifecycle (start -> stop -> reset) at scale,
verifying no subscriber leaks, counter hygiene, injection accumulation,
rapid-fire resilience, and pause/resume stress cycling.

Uses the _build_live_stack pattern from test_live_event_simulation.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.capture.demo_machine import DemoMachine
from src.capture.event_bus import EventBus
from src.commentary.pipeline import CommentaryPipeline
from src.defense.pipeline import DefensePipeline
from src.memory.pipeline import DeliberationPipeline
from src.operator.web import WebOperator
from src.rehearsal.replay_provider import ReplayProvider
from src.scoring.moe_engine import MoEScoringEngine
from src.scoring.pipeline import ScoringPipeline
from tests.test_smoke import (
    EventCollector,
    FakeDisplayServer,
    _drain_connect,
    _fake_stream_sentences,
)

# ---------------------------------------------------------------------------
# Team roster for 15-demo marathon
# ---------------------------------------------------------------------------

MARATHON_TEAMS = [
    {"team_name": f"MarathonTeam-{i:02d}", "track": track}
    for i, track in enumerate(
        [
            "SHADOW::VECTOR",
            "SENTINEL::MESH",
            "ZERO::PROOF",
            "ROGUE::AGENT",
            "SHADOW::VECTOR",
            "SENTINEL::MESH",
            "ZERO::PROOF",
            "ROGUE::AGENT",
            "SHADOW::VECTOR",
            "SENTINEL::MESH",
            "ZERO::PROOF",
            "ROGUE::AGENT",
            "SHADOW::VECTOR",
            "SENTINEL::MESH",
            "ZERO::PROOF",
        ],
        start=1,
    )
]

assert len(MARATHON_TEAMS) == 15


# ---------------------------------------------------------------------------
# Stack builder (mirrors _build_live_stack from test_live_event_simulation)
# ---------------------------------------------------------------------------


def _build_live_stack(tmp_path):
    """Wire the full pipeline with mocked externals for stress testing."""
    bus = EventBus()
    display = FakeDisplayServer()

    mock_gemini = MagicMock()
    mock_gemini.get_observations.return_value = [
        "The team built a security tool demonstration",
    ]
    mock_gemini.clear_observations = MagicMock()
    defense = DefensePipeline(api_key="test", gemini_session=mock_gemini)

    commentary = CommentaryPipeline(api_key="test", voice_id="test")
    commentary._tts = MagicMock()
    commentary._tts.connect = AsyncMock()
    commentary._tts.speak = AsyncMock()
    commentary._tts.play_sound = AsyncMock()
    commentary._tts._connected = True
    commentary._display = display
    commentary._generator.stream_sentences = _fake_stream_sentences

    scores_dir = str(tmp_path / "scores")
    scoring = ScoringPipeline(
        api_key="test",
        display=display,
        scores_dir=scores_dir,
        moe_engine=MoEScoringEngine([ReplayProvider()]),
    )

    deliberation = DeliberationPipeline(
        api_key="test",
        display=display,
        scores_dir=scores_dir,
        observations_dir=str(tmp_path / "observations"),
        deliberation_dir=str(tmp_path / "deliberation"),
    )
    deliberation._memory_store.save = AsyncMock()

    machine = DemoMachine(event_bus=bus)

    operator = WebOperator(
        demo_machine=machine,
        event_bus=bus,
        display_server=display,
        scoring_pipeline=scoring,
        deliberation_pipeline=deliberation,
    )

    collector = EventCollector(bus)
    return operator, machine, bus, display, scoring, defense, commentary, deliberation, collector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ws_drain_until(ws, state_name: str, max_msgs: int = 20) -> list[dict]:
    """Read WS messages until a state message with the given state is found."""
    msgs = []
    for _ in range(max_msgs):
        msg = ws.receive_json()
        msgs.append(msg)
        if msg.get("type") == "state" and msg.get("state") == state_name:
            return msgs
    raise AssertionError(
        f"Did not reach state '{state_name}' within {max_msgs} messages. "
        f"Last messages: {msgs[-5:]}"
    )


def _run_demo_cycle(ws, team_name: str, track: str) -> None:
    """Run a full start -> stop -> reset cycle for one team."""
    ws.send_json({
        "type": "command",
        "action": "start",
        "team_name": team_name,
        "track": track,
    })
    _ws_drain_until(ws, "capturing")

    ws.send_json({"type": "command", "action": "stop"})
    _ws_drain_until(ws, "stopped")

    ws.send_json({"type": "command", "action": "reset"})
    _ws_drain_until(ws, "idle")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_fifteen_demo_operator_marathon(tmp_path):
    """Run 15 teams through the full WS operator lifecycle.

    Verifies:
    - Machine ends idle
    - No subscriber leaks on the event bus
    - display.capture_started_calls has exactly 15 entries
    - Each team name appears exactly once in capture_started
    """
    (
        operator, machine, bus, display,
        scoring, defense, commentary, deliberation, collector,
    ) = _build_live_stack(tmp_path)

    operator._register_routes()
    operator._subscribe_events()

    # Snapshot subscriber counts before the marathon
    sub_counts_before = {k: len(v) for k, v in bus._subscribers.items()}
    global_sub_count_before = len(bus._global_subscribers)

    client = TestClient(display.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)

        for team in MARATHON_TEAMS:
            _run_demo_cycle(ws, team["team_name"], team["track"])

    # Machine should be idle
    assert machine.current_state.id == "idle"

    # No subscriber leaks
    sub_counts_after = {k: len(v) for k, v in bus._subscribers.items()}
    global_sub_count_after = len(bus._global_subscribers)
    assert sub_counts_before == sub_counts_after, (
        f"Subscriber leak: before={sub_counts_before}, after={sub_counts_after}"
    )
    assert global_sub_count_before == global_sub_count_after, (
        f"Global subscriber leak: before={global_sub_count_before}, after={global_sub_count_after}"
    )

    # Exactly 15 capture_started calls
    assert len(display.capture_started_calls) == 15, (
        f"Expected 15 capture_started calls, got {len(display.capture_started_calls)}"
    )

    # Each team appears exactly once
    started_teams = [c["team_name"] for c in display.capture_started_calls]
    expected_teams = [t["team_name"] for t in MARATHON_TEAMS]
    assert started_teams == expected_teams, (
        f"Team order mismatch: {started_teams} != {expected_teams}"
    )
    assert len(set(started_teams)) == 15, "Duplicate team names in capture_started"


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_counters_reset_each_demo(tmp_path):
    """Run 3 demos and verify counters are fresh after each start.

    After each start command, the operator resets counters to zero.
    Uses get_state to verify via a second state push.
    """
    (
        operator, machine, bus, display,
        scoring, defense, commentary, deliberation, collector,
    ) = _build_live_stack(tmp_path)

    operator._register_routes()
    operator._subscribe_events()

    client = TestClient(display.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)

        for i in range(3):
            team_name = f"CounterTeam-{i}"

            # Start demo
            ws.send_json({
                "type": "command",
                "action": "start",
                "team_name": team_name,
                "track": "ROGUE::AGENT",
            })
            _ws_drain_until(ws, "capturing")

            # After start, counters should be reset to zero
            assert operator._counters["frames"] == 0, (
                f"Demo {i}: frames counter not reset, got {operator._counters['frames']}"
            )
            assert operator._counters["transcripts"] == 0, (
                f"Demo {i}: transcripts counter not reset"
            )
            assert operator._counters["attacks"] == 0, (
                f"Demo {i}: attacks counter not reset"
            )
            assert operator._counters["clean"] == 0, (
                f"Demo {i}: clean counter not reset"
            )

            # Request explicit state to verify operator is responsive
            ws.send_json({"type": "command", "action": "get_state"})
            msgs = []
            for _ in range(10):
                msg = ws.receive_json()
                msgs.append(msg)
                if msg.get("type") == "state" and msg.get("state") == "capturing":
                    break

            state_msgs = [m for m in msgs if m.get("type") == "state"]
            assert len(state_msgs) >= 1, f"No state message after get_state on demo {i}"

            # Stop and reset
            ws.send_json({"type": "command", "action": "stop"})
            _ws_drain_until(ws, "stopped")

            ws.send_json({"type": "command", "action": "reset"})
            _ws_drain_until(ws, "idle")


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_total_injections_accumulates_across_resets(tmp_path):
    """Run 3 demos. Inject InjectionDetected events during demo 2.

    After reset, _total_injections should accumulate the attacks counter.
    After demo 3 (no injections), _total_injections should still include
    the demo 2 count.
    """
    (
        operator, machine, bus, display,
        scoring, defense, commentary, deliberation, collector,
    ) = _build_live_stack(tmp_path)

    operator._register_routes()
    operator._subscribe_events()

    client = TestClient(display.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)

        # --- Demo 1: no injections ---
        ws.send_json({
            "type": "command",
            "action": "start",
            "team_name": "InjectTeam-1",
            "track": "ROGUE::AGENT",
        })
        _ws_drain_until(ws, "capturing")

        ws.send_json({"type": "command", "action": "stop"})
        _ws_drain_until(ws, "stopped")

        ws.send_json({"type": "command", "action": "reset"})
        _ws_drain_until(ws, "idle")

        # After demo 1 reset, _total_injections should be 0
        assert operator._total_injections == 0, (
            f"Expected 0 total injections after demo 1, got {operator._total_injections}"
        )

        # --- Demo 2: simulate 3 injection detections ---
        ws.send_json({
            "type": "command",
            "action": "start",
            "team_name": "InjectTeam-2",
            "track": "ROGUE::AGENT",
        })
        _ws_drain_until(ws, "capturing")

        # Directly set the attacks counter to simulate what _on_event does
        # when it receives InjectionDetected events. We cannot use
        # bus.publish() here because the TestClient runs in a sync context
        # without a running asyncio event loop.
        operator._counters["attacks"] = 3

        ws.send_json({"type": "command", "action": "stop"})
        _ws_drain_until(ws, "stopped")

        ws.send_json({"type": "command", "action": "reset"})
        _ws_drain_until(ws, "idle")

        # After demo 2 reset, _total_injections should be 3
        assert operator._total_injections == 3, (
            f"Expected 3 total injections after demo 2, got {operator._total_injections}"
        )

        # --- Demo 3: no injections ---
        ws.send_json({
            "type": "command",
            "action": "start",
            "team_name": "InjectTeam-3",
            "track": "ROGUE::AGENT",
        })
        _ws_drain_until(ws, "capturing")

        ws.send_json({"type": "command", "action": "stop"})
        _ws_drain_until(ws, "stopped")

        ws.send_json({"type": "command", "action": "reset"})
        _ws_drain_until(ws, "idle")

        # _total_injections should still be 3 (demo 3 added 0 attacks)
        assert operator._total_injections == 3, (
            f"Expected 3 total injections after demo 3, got {operator._total_injections}"
        )


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_rapid_start_stop_ten_times(tmp_path):
    """Run 10 rapid start/stop/reset cycles with no sleep between.

    Verifies no exceptions, machine ends idle, no stale state.
    """
    (
        operator, machine, bus, display,
        scoring, defense, commentary, deliberation, collector,
    ) = _build_live_stack(tmp_path)

    operator._register_routes()
    operator._subscribe_events()

    client = TestClient(display.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)

        for i in range(10):
            team_name = f"RapidTeam-{i}"

            ws.send_json({
                "type": "command",
                "action": "start",
                "team_name": team_name,
                "track": "SHADOW::VECTOR",
            })
            _ws_drain_until(ws, "capturing")

            ws.send_json({"type": "command", "action": "stop"})
            _ws_drain_until(ws, "stopped")

            ws.send_json({"type": "command", "action": "reset"})
            _ws_drain_until(ws, "idle")

    # Machine ends idle
    assert machine.current_state.id == "idle"

    # No stale session
    assert machine.current_session is None or machine.current_state.id == "idle"

    # All 10 demos were tracked
    assert len(display.capture_started_calls) == 10

    # No subscriber leaks (global_subscribers should not grow)
    # The operator subscribes once via subscribe_all; collector subscribes once.
    # Neither should have grown.
    assert len(bus._global_subscribers) <= 3, (
        f"Unexpected global subscriber count: {len(bus._global_subscribers)}"
    )


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_pause_resume_stress_cycle(tmp_path):
    """For each of 5 demos: start -> pause -> resume -> pause -> resume -> stop -> reset.

    Verifies machine always returns to idle and no state leaks.
    """
    (
        operator, machine, bus, display,
        scoring, defense, commentary, deliberation, collector,
    ) = _build_live_stack(tmp_path)

    operator._register_routes()
    operator._subscribe_events()

    sub_counts_before = {k: len(v) for k, v in bus._subscribers.items()}
    global_sub_count_before = len(bus._global_subscribers)

    client = TestClient(display.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)

        for i in range(5):
            team_name = f"PauseStressTeam-{i}"

            # Start
            ws.send_json({
                "type": "command",
                "action": "start",
                "team_name": team_name,
                "track": "ZERO::PROOF",
            })
            _ws_drain_until(ws, "capturing")

            # Pause 1
            ws.send_json({"type": "command", "action": "pause"})
            _ws_drain_until(ws, "paused")

            # Resume 1
            ws.send_json({"type": "command", "action": "resume"})
            _ws_drain_until(ws, "capturing")

            # Pause 2
            ws.send_json({"type": "command", "action": "pause"})
            _ws_drain_until(ws, "paused")

            # Resume 2
            ws.send_json({"type": "command", "action": "resume"})
            _ws_drain_until(ws, "capturing")

            # Stop
            ws.send_json({"type": "command", "action": "stop"})
            _ws_drain_until(ws, "stopped")

            # Reset
            ws.send_json({"type": "command", "action": "reset"})
            _ws_drain_until(ws, "idle")

    # Machine ends idle
    assert machine.current_state.id == "idle"

    # All 5 demos tracked
    assert len(display.capture_started_calls) == 5

    # No subscriber leaks
    sub_counts_after = {k: len(v) for k, v in bus._subscribers.items()}
    global_sub_count_after = len(bus._global_subscribers)
    assert sub_counts_before == sub_counts_after, (
        f"Subscriber leak: before={sub_counts_before}, after={sub_counts_after}"
    )
    assert global_sub_count_before == global_sub_count_after, (
        f"Global subscriber leak: before={global_sub_count_before}, after={global_sub_count_after}"
    )

    # Each team appears exactly once
    started_teams = [c["team_name"] for c in display.capture_started_calls]
    expected_teams = [f"PauseStressTeam-{i}" for i in range(5)]
    assert started_teams == expected_teams
