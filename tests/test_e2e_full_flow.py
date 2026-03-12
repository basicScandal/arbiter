"""Comprehensive end-to-end integration tests for the Arbiter WebOperator HTTP/WS API.

Exercises the full user-facing flow experienced by the operator dashboard and
audience display, covering four flows:

  Flow 1 -- Full Demo Lifecycle via WebSocket
  Flow 2 -- Report Card + Export API
  Flow 3 -- Human Score Integration
  Flow 4 -- Multi-client Broadcast

Uses FastAPI TestClient for HTTP and WebSocket testing with real EventBus,
DemoMachine, and WebOperator instances. External dependencies (LLM, TTS, file
paths) are redirected or mocked so every test is fully self-contained.

Pattern references:
  - tests/test_web_operator.py  (FakeDisplayServer, _make_operator, _drain_connect)
  - tests/test_e2e_pipeline_chain.py (event ordering assertions)
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

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
from src.operator.web import WebOperator
from src.scoring.models import CriterionScore, DemoScorecard, ScoringComplete

# ---------------------------------------------------------------------------
# Fake collaborators (mirrored from test_web_operator.py)
# ---------------------------------------------------------------------------


class FakeDisplayServer:
    """Minimal DisplayServer stand-in that owns a real FastAPI app."""

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
        self.intermission_calls.append(
            {"leaderboard": leaderboard, "total_injections": total_injections}
        )

    async def push_injection_blocked(
        self, category: str, confidence: str, roast: str, team_name: str
    ) -> None:
        self.injection_blocked_calls.append(
            {"category": category, "confidence": confidence, "roast": roast, "team_name": team_name}
        )


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


# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------


def _make_operator(
    bus: EventBus | None = None,
    scoring: FakeScoringPipeline | None = None,
    deliberation: FakeDeliberationPipeline | None = None,
) -> tuple[WebOperator, DemoMachine, EventBus, FakeDisplayServer]:
    """Return a fully wired WebOperator with all routes registered."""
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
    """Consume the three messages sent on WebSocket connect.

    On connect, _push_state emits: state, health, scoring_phase.
    Tests must drain all three before reading command responses.

    Returns the state message so tests can inspect it.
    """
    state = ws.receive_json()
    assert state["type"] == "state", f"Expected 'state', got {state.get('type')}"
    health = ws.receive_json()
    assert health["type"] == "health", f"Expected 'health', got {health.get('type')}"
    scoring_phase = ws.receive_json()
    assert scoring_phase["type"] == "scoring_phase"
    return state


def _make_scorecard(
    team_name: str = "Alpha",
    track: str = "ROGUE::AGENT",
    total_score: float = 7.5,
) -> DemoScorecard:
    """Build a minimal but valid DemoScorecard for testing."""
    return DemoScorecard(
        team_name=team_name,
        track=track,
        criteria=[
            CriterionScore(
                name="Technical Execution",
                score=8.0,
                weight=0.40,
                justification="Solid implementation with clean code.",
            ),
            CriterionScore(
                name="Innovation",
                score=7.0,
                weight=0.30,
                justification="Novel approach to the problem.",
            ),
            CriterionScore(
                name="Demo Quality",
                score=7.0,
                weight=0.30,
                justification="Smooth presentation.",
            ),
        ],
        track_bonus=None,
        total_score=total_score,
        scored_at=time.time(),
    )


# ---------------------------------------------------------------------------
# Flow 1: Full Demo Lifecycle via WebSocket
# ---------------------------------------------------------------------------


def test_ws_connect_receives_idle_state():
    """Operator connects via WS and immediately receives the initial idle state."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        state = _drain_connect(ws)

    assert state["state"] == "idle"
    assert state["team_name"] == ""
    assert state["started_at"] is None
    assert state["track"] == ""


def test_ws_start_transitions_to_capturing():
    """Operator sends START → DemoMachine transitions to capturing with broadcast."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)

        ws.send_json(
            {"type": "command", "action": "start", "team_name": "Alpha", "track": "ROGUE::AGENT"}
        )

        result = ws.receive_json()
        assert result["type"] == "command_result"
        assert result["success"] is True
        assert "Alpha" in result["message"]

        state = ws.receive_json()
        assert state["type"] == "state"
        assert state["state"] == "capturing"
        assert state["team_name"] == "Alpha"
        assert state["track"] == "ROGUE::AGENT"

    assert machine.current_state.id == "capturing"


@pytest.mark.asyncio
async def test_ws_events_update_counters_and_broadcast():
    """Synthetic frame and transcript events increment counters on the operator."""
    op, machine, bus, ds = _make_operator()

    # Start the machine so events are meaningful
    machine.send("start_demo", team_name="Beta")

    frame_event = KeyFrameDetected(
        frame=FrameData(jpeg_data=b"\xff", width=1, height=1, timestamp=0.0)
    )
    transcript_event = TranscriptReceived(
        segment=TranscriptSegment(text="Hello world", timestamp=0.0)
    )

    await op._on_event(frame_event)
    await op._on_event(frame_event)
    await op._on_event(transcript_event)

    assert op._counters["frames"] == 2
    assert op._counters["transcripts"] == 1


def test_ws_stop_transitions_to_stopped():
    """Operator sends STOP → state transitions to stopped with duration in message."""
    op, machine, bus, ds = _make_operator()
    machine.send("start_demo", team_name="Gamma")
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        _drain_connect(ws)

        ws.send_json({"type": "command", "action": "stop"})

        result = ws.receive_json()
        assert result["type"] == "command_result"
        assert result["success"] is True
        assert "Gamma" in result["message"]
        assert "duration" in result["message"].lower()

        state = ws.receive_json()
        assert state["type"] == "state"
        assert state["state"] == "stopped"

    assert machine.current_state.id == "stopped"


@pytest.mark.asyncio
async def test_ws_stop_triggers_scoring_phase_sanitizing():
    """After STOP, the scoring_phase message with 'sanitizing' is broadcast.

    The DemoStopped event is published by DemoMachine; WebOperator handles it
    via _on_event and calls _push_scoring_phase('sanitizing'). We verify the
    stored phase value on the operator object after event handling.
    """
    from src.capture.models import DemoStopped

    op, machine, bus, ds = _make_operator()
    machine.send("start_demo", team_name="Delta")

    await op._on_event(DemoStopped(team_name="Delta"))

    assert op._scoring_phase == "sanitizing"


@pytest.mark.asyncio
async def test_ws_scoring_complete_event_broadcast_contains_scorecard():
    """scoring_complete event broadcast includes the full scorecard payload."""
    op, machine, bus, ds = _make_operator()

    captured = []

    async def capture_broadcast(msg):
        captured.append(msg)

    op._broadcast_to_operators = capture_broadcast

    scorecard = _make_scorecard(team_name="Echo", track="ZERO::PROOF")
    event = ScoringComplete(scorecard=scorecard)

    await op._on_event(event)

    event_msgs = [m for m in captured if m.get("type") == "event"]
    assert len(event_msgs) >= 1

    sc_msg = next(
        (m for m in event_msgs if m.get("event_type") == "scoring_complete"), None
    )
    assert sc_msg is not None, "No scoring_complete event message was broadcast"
    sc_data = sc_msg["data"]["scorecard"]
    assert sc_data["team_name"] == "Echo"
    assert sc_data["track"] == "ZERO::PROOF"
    assert sc_data["total_score"] == scorecard.total_score


def test_ws_full_lifecycle_idle_to_stopped():
    """Complete operator lifecycle: idle -> capturing -> stopped verified via WS."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        state = _drain_connect(ws)
        assert state["state"] == "idle"

        # Start
        ws.send_json(
            {"type": "command", "action": "start", "team_name": "Foxtrot", "track": "SHADOW::VECTOR"}
        )
        result = ws.receive_json()
        assert result["success"] is True
        state = ws.receive_json()
        assert state["state"] == "capturing"
        assert state["team_name"] == "Foxtrot"

        # Stop
        ws.send_json({"type": "command", "action": "stop"})
        result = ws.receive_json()
        assert result["success"] is True
        state = ws.receive_json()
        assert state["state"] == "stopped"

    assert machine.current_state.id == "stopped"


# ---------------------------------------------------------------------------
# Flow 2: Report Card + Export API
# ---------------------------------------------------------------------------


def test_report_card_returns_html_with_team_name_and_score(tmp_path):
    """GET /api/report-card/{team_name} returns HTML containing team name and score."""
    scorecard = _make_scorecard(team_name="Foxtrot", track="ROGUE::AGENT", total_score=8.2)
    scores_dir = tmp_path / "scores"
    scores_dir.mkdir()

    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with (
        patch("src.reports.card.SCORES_DIR", scores_dir),
        patch("src.scoring.store.ScoreStore.__init__", lambda self, scores_dir=None: None),
        patch("src.scoring.store.ScoreStore.load", AsyncMock(return_value=scorecard)),
    ):
        response = client.get("/api/report-card/Foxtrot")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert "Foxtrot" in body
    assert "8.2" in body


def test_report_card_returns_404_for_unknown_team(tmp_path):
    """GET /api/report-card/{team_name} returns 404 when team has no scorecard."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with (
        patch("src.scoring.store.ScoreStore.load", AsyncMock(return_value=None)),
        patch("src.reports.card.SCORES_DIR", tmp_path / "scores"),
    ):
        response = client.get("/api/report-card/NoSuchTeam")

    assert response.status_code == 404
    body = response.json()
    assert "error" in body


def test_report_cards_list_returns_sorted_json(tmp_path):
    """GET /api/report-cards returns sorted JSON list of all scorecards."""
    scorecards = [
        _make_scorecard("TeamA", total_score=6.0),
        _make_scorecard("TeamB", total_score=9.1),
    ]

    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with patch("src.scoring.store.ScoreStore.load_all", AsyncMock(return_value=scorecards)):
        response = client.get("/api/report-cards")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Should be sorted descending by total_score
    assert data[0]["total_score"] >= data[1]["total_score"]
    team_names = {item["team_name"] for item in data}
    assert "TeamA" in team_names
    assert "TeamB" in team_names


def test_export_team_returns_team_json(tmp_path):
    """GET /api/export/{team_name} returns team export JSON with scorecard data."""
    scorecard = _make_scorecard(team_name="Golf", track="SENTINEL::MESH", total_score=7.7)

    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with (
        patch("src.reports.export.SCORES_DIR", tmp_path / "scores"),
        patch("src.reports.export.COMMENTARY_DIR", tmp_path / "commentary"),
        patch("src.reports.export.OBSERVATIONS_DIR", tmp_path / "observations"),
        patch("src.reports.export.HUMAN_SCORES_DIR", tmp_path / "human_scores"),
        patch("src.scoring.store.ScoreStore.load", AsyncMock(return_value=scorecard)),
    ):
        response = client.get("/api/export/Golf")

    assert response.status_code == 200
    data = response.json()
    assert data["team_name"] == "Golf"
    assert data["track"] == "SENTINEL::MESH"
    assert data["ai_score"] == 7.7
    assert "scorecard" in data


def test_export_team_returns_404_for_unknown_team(tmp_path):
    """GET /api/export/{team_name} returns 404 when team has no scorecard."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with (
        patch("src.reports.export.SCORES_DIR", tmp_path / "scores"),
        patch("src.scoring.store.ScoreStore.load", AsyncMock(return_value=None)),
    ):
        response = client.get("/api/export/Ghost")

    assert response.status_code == 404


def test_export_all_returns_event_export_json(tmp_path):
    """GET /api/export returns full event export JSON with team count."""
    scorecards = [
        _make_scorecard("Hotel", total_score=8.0),
        _make_scorecard("India", total_score=6.5),
    ]

    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with (
        patch("src.reports.export.SCORES_DIR", tmp_path / "scores"),
        patch("src.reports.export.COMMENTARY_DIR", tmp_path / "commentary"),
        patch("src.reports.export.OBSERVATIONS_DIR", tmp_path / "observations"),
        patch("src.reports.export.HUMAN_SCORES_DIR", tmp_path / "human_scores"),
        patch("src.reports.export.DELIBERATION_DIR", tmp_path / "deliberation"),
        patch("src.reports.export.AUDIT_LOG", tmp_path / "audit.jsonl"),
        patch("src.scoring.store.ScoreStore.load_all", AsyncMock(return_value=scorecards)),
    ):
        response = client.get("/api/export")

    assert response.status_code == 200
    data = response.json()
    assert data["team_count"] == 2
    assert data["event_name"] == "NEBULA:FOG 2026"
    assert "teams" in data
    assert len(data["teams"]) == 2


# ---------------------------------------------------------------------------
# Flow 3: Human Score Integration
# ---------------------------------------------------------------------------


def test_post_human_score_persists_and_returns_ok(tmp_path):
    """POST /api/human-score accepts a human judge score and returns ok."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    human_scores_dir = tmp_path / "human_scores"
    human_scores_dir.mkdir()

    payload = {
        "judge_name": "Judge Dredd",
        "team_name": "Juliet",
        "total_score": 8.5,
        "notes": "Impressive injection resistance.",
    }

    with patch("src.scoring.human.HUMAN_SCORES_DIR", human_scores_dir):
        response = client.post("/api/human-score", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["team_name"] == "Juliet"
    assert data["judge"] == "Judge Dredd"


def test_post_human_score_validates_required_fields():
    """POST /api/human-score returns 400 when required fields are missing."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    # Missing judge_name
    payload = {"team_name": "Kilo", "total_score": 7.0}
    response = client.post("/api/human-score", json=payload)
    assert response.status_code == 400


def test_blended_score_returns_ai_only_when_no_human_scores(tmp_path):
    """GET /api/blended-score/{team_name} returns AI-only blend when no human scores exist."""
    scorecard = _make_scorecard(team_name="Lima", total_score=7.5)
    human_scores_dir = tmp_path / "human_scores"
    human_scores_dir.mkdir()

    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with (
        patch("src.scoring.human.HUMAN_SCORES_DIR", human_scores_dir),
        patch("src.scoring.store.ScoreStore.load", AsyncMock(return_value=scorecard)),
    ):
        response = client.get("/api/blended-score/Lima")

    assert response.status_code == 200
    data = response.json()
    assert data["team_name"] == "Lima"
    assert data["ai_score"] == 7.5
    # No human scores → blended == ai score
    assert data["blended_score"] == 7.5
    assert data["human_judges"] == []


def test_blended_score_with_human_judge_score(tmp_path):
    """GET /api/blended-score/{team_name} blends AI + human score at 70/30 weight."""
    from src.scoring.human import HumanScore

    scorecard = _make_scorecard(team_name="Mike", total_score=8.0)
    human_score = HumanScore(
        judge_name="Judge A",
        team_name="Mike",
        total_score=6.0,
        submitted_at=time.time(),
    )

    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with (
        patch("src.scoring.store.ScoreStore.load", AsyncMock(return_value=scorecard)),
        patch("src.scoring.human.HumanScoreStore.load", AsyncMock(return_value=[human_score])),
    ):
        response = client.get("/api/blended-score/Mike")

    assert response.status_code == 200
    data = response.json()
    # Expected: 0.7 * 8.0 + 0.3 * 6.0 = 5.6 + 1.8 = 7.4
    assert abs(data["blended_score"] - 7.4) < 0.05
    assert len(data["human_judges"]) == 1


def test_blended_score_returns_404_for_unknown_team(tmp_path):
    """GET /api/blended-score/{team_name} returns 404 when no AI scorecard exists."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with patch("src.scoring.store.ScoreStore.load", AsyncMock(return_value=None)):
        response = client.get("/api/blended-score/NoTeam")

    assert response.status_code == 404


def test_blended_scores_all_returns_list(tmp_path):
    """GET /api/blended-scores returns a ranked list of all blended scores."""

    scorecards = [
        _make_scorecard("November", total_score=7.0),
        _make_scorecard("Oscar", total_score=9.0),
    ]

    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with (
        patch("src.scoring.store.ScoreStore.load_all", AsyncMock(return_value=scorecards)),
        patch("src.scoring.human.HumanScoreStore.load", AsyncMock(return_value=[])),
        # blend_scores also calls ScoreStore.load per team
        patch("src.scoring.store.ScoreStore.load", AsyncMock(side_effect=scorecards)),
    ):
        response = client.get("/api/blended-scores")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Should be sorted descending by blended_score
    assert data[0]["blended_score"] >= data[1]["blended_score"]


# ---------------------------------------------------------------------------
# Flow 4: Multi-client Broadcast
# ---------------------------------------------------------------------------


def test_two_ws_clients_both_receive_state_broadcast():
    """Two concurrent WS clients both receive state broadcasts after a command."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws1:
        _drain_connect(ws1)

        with client.websocket_connect("/ws/operator") as ws2:
            _drain_connect(ws2)

            assert len(op._operator_connections) == 2

            # Send start from ws1
            ws1.send_json(
                {"type": "command", "action": "start", "team_name": "Papa", "track": "ROGUE::AGENT"}
            )

            # ws1 receives command_result then state
            r1 = ws1.receive_json()
            assert r1["type"] == "command_result"
            assert r1["success"] is True

            s1 = ws1.receive_json()
            assert s1["type"] == "state"
            assert s1["state"] == "capturing"

            # ws2 also receives the broadcast state (no command_result for ws2)
            s2 = ws2.receive_json()
            assert s2["type"] == "state"
            assert s2["state"] == "capturing"
            assert s2["team_name"] == "Papa"


def test_disconnected_client_removed_from_active_connections():
    """After one client disconnects, remaining client still works normally."""
    op, machine, bus, ds = _make_operator()
    client = TestClient(ds.app)

    # Connect first client and disconnect it
    with client.websocket_connect("/ws/operator") as ws1:
        _drain_connect(ws1)
        assert len(op._operator_connections) == 1

    # ws1 has disconnected
    assert len(op._operator_connections) == 0

    # Second client connects fresh and can still operate
    with client.websocket_connect("/ws/operator") as ws2:
        state = _drain_connect(ws2)
        assert state["state"] == "idle"
        assert len(op._operator_connections) == 1

        ws2.send_json(
            {"type": "command", "action": "start", "team_name": "Quebec", "track": "ZERO::PROOF"}
        )
        result = ws2.receive_json()
        assert result["success"] is True

    assert len(op._operator_connections) == 0


def test_second_client_receives_current_state_on_connect():
    """A client that connects mid-demo receives the current capturing state."""
    op, machine, bus, ds = _make_operator()
    # Pre-start the demo
    machine.send("start_demo", team_name="Romeo")

    client = TestClient(ds.app)

    with client.websocket_connect("/ws/operator") as ws:
        state = _drain_connect(ws)

    assert state["state"] == "capturing"
    assert state["team_name"] == "Romeo"
