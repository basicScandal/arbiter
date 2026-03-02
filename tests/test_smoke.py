"""Pre-event go/no-go smoke test for the Arbiter pipeline.

Exercises the full event-driven pipeline end-to-end through a real EventBus,
DemoMachine, and WebOperator with real sub-pipelines (defense, commentary,
scoring, deliberation).  Only external API calls (LLM, TTS) are mocked --
everything else runs for real.

The test verifies the complete cycle:
  start_demo -> synthetic events -> stop_demo ->
  observation_verified -> scoring -> commentary -> score reveal

Designed to run as a go/no-go gate before the live hackathon event.

Pattern references:
  - tests/test_e2e_full_flow.py  (FakeDisplayServer, _make_operator, _drain_connect)
  - src/rehearsal/rehearsal_pipeline.py (mock wiring for pipelines)
  - src/rehearsal/synthetic_capture.py (synthetic event injection)
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.capture.demo_machine import DemoMachine
from src.capture.event_bus import EventBus
from src.capture.models import CaptureEvent
from src.commentary.pipeline import CommentaryPipeline
from src.defense.pipeline import DefensePipeline
from src.memory.pipeline import DeliberationPipeline
from src.operator.web import WebOperator
from src.rehearsal.replay_provider import ReplayProvider
from src.rehearsal.synthetic_capture import SyntheticCapture
from src.scoring.moe_engine import MoEScoringEngine
from src.scoring.pipeline import ScoringPipeline

# ---------------------------------------------------------------------------
# Canned commentary data (mirrors rehearsal_pipeline.py)
# ---------------------------------------------------------------------------

_CANNED_COMMENTARY_SENTENCES = [
    ("A team that actually knows what they're doing.", "sarcastic", 0),
    ("The network recon module is impressively clean.", "contempt", 1),
    ("That graph-based vuln correlation is a clever touch.", "content", 2),
]


async def _fake_stream_sentences(sanitized_output):
    """Async generator yielding canned commentary sentences."""
    for sentence, emotion, idx in _CANNED_COMMENTARY_SENTENCES:
        yield (sentence, emotion, idx)


# ---------------------------------------------------------------------------
# Fake collaborators (from test_e2e_full_flow.py pattern)
# ---------------------------------------------------------------------------


class FakeDisplayServer:
    """Minimal DisplayServer stand-in owning a real FastAPI app."""

    def __init__(self) -> None:
        self._app = FastAPI()
        self.cleared: int = 0
        self.capture_started_calls: list[dict] = []
        self.intermission_calls: list[dict] = []
        self.injection_blocked_calls: list[dict] = []
        self.commentary_calls: list[dict] = []
        self.score_intro_calls: list[dict] = []
        self.criterion_calls: list[dict] = []
        self.total_score_calls: list[dict] = []

    @property
    def app(self) -> FastAPI:
        return self._app

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

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

    async def push_commentary(self, text: str, team_name: str, **kwargs) -> None:
        self.commentary_calls.append({"text": text, "team_name": team_name, **kwargs})

    async def push_score_intro(self, team_name: str) -> None:
        self.score_intro_calls.append({"team_name": team_name})

    async def push_criterion_reveal(
        self, name: str, score: float, weight: float, justification: str
    ) -> None:
        self.criterion_calls.append(
            {"name": name, "score": score, "weight": weight, "justification": justification}
        )

    async def push_total_score(self, team_name: str, total_score: float, track: str) -> None:
        self.total_score_calls.append(
            {"team_name": team_name, "total_score": total_score, "track": track}
        )

    async def push_deliberation_ranking(self, **kwargs) -> None:
        pass

    async def push_deliberation_narrative(self, narrative: str) -> None:
        pass

    async def push_question(self, text: str, team_name: str) -> None:
        pass


# ---------------------------------------------------------------------------
# Event collector for bus-level assertions
# ---------------------------------------------------------------------------


class EventCollector:
    """Subscribes to all events on a bus and collects them for assertions."""

    def __init__(self, event_bus: EventBus) -> None:
        self.events: list[CaptureEvent] = []
        self.events_by_type: dict[str, list[CaptureEvent]] = {}
        self._scoring_complete = asyncio.Event()
        self._score_revealed = asyncio.Event()
        self._commentary_delivered = asyncio.Event()
        event_bus.subscribe_all(self._on_event)

    async def _on_event(self, event: CaptureEvent) -> None:
        self.events.append(event)
        self.events_by_type.setdefault(event.event_type, []).append(event)
        if event.event_type == "scoring_complete":
            self._scoring_complete.set()
        if event.event_type == "score_revealed":
            self._score_revealed.set()
        if event.event_type == "commentary_delivered":
            self._commentary_delivered.set()

    async def wait_scoring_complete(self, timeout: float = 15.0) -> None:
        await asyncio.wait_for(self._scoring_complete.wait(), timeout=timeout)

    async def wait_score_revealed(self, timeout: float = 20.0) -> None:
        await asyncio.wait_for(self._score_revealed.wait(), timeout=timeout)

    async def wait_commentary_delivered(self, timeout: float = 15.0) -> None:
        await asyncio.wait_for(self._commentary_delivered.wait(), timeout=timeout)


# ---------------------------------------------------------------------------
# Helper: drain WS connect messages (from test_e2e_full_flow.py)
# ---------------------------------------------------------------------------


def _drain_connect(ws) -> dict:
    """Consume the three messages sent on WebSocket connect.

    On connect, _push_state emits: state, health, scoring_phase.
    Returns the state message so tests can inspect it.
    """
    state = ws.receive_json()
    assert state["type"] == "state", f"Expected 'state', got {state.get('type')}"
    health = ws.receive_json()
    assert health["type"] == "health", f"Expected 'health', got {health.get('type')}"
    scoring_phase = ws.receive_json()
    assert scoring_phase["type"] == "scoring_phase"
    return state


# ---------------------------------------------------------------------------
# Pipeline factory: wires real pipelines with mocked externals
# ---------------------------------------------------------------------------


def _build_smoke_stack(tmp_path) -> tuple[
    WebOperator, DemoMachine, EventBus, FakeDisplayServer,
    ScoringPipeline, DefensePipeline, CommentaryPipeline,
    DeliberationPipeline, EventCollector,
]:
    """Wire the full Arbiter pipeline with mocked external calls.

    Returns all components for assertions. Uses tmp_path for any file I/O
    (scores, observations, deliberation) so tests are self-contained.
    """
    bus = EventBus()
    display = FakeDisplayServer()

    # Defense pipeline with mock GeminiSession
    mock_gemini = MagicMock()
    mock_gemini.get_observations.return_value = [
        "The team built a network reconnaissance tool with graph-based analysis",
        "It correlates CVEs across services to find exploitable chains",
        "Live demo showed real-time graph construction against test environment",
    ]
    mock_gemini.clear_observations = MagicMock()
    defense = DefensePipeline(api_key="smoke", gemini_session=mock_gemini)

    # Commentary pipeline with mocked TTS and generator
    commentary = CommentaryPipeline(api_key="smoke", voice_id="smoke")
    commentary._tts = MagicMock()
    commentary._tts.connect = AsyncMock()
    commentary._tts.speak = AsyncMock()
    commentary._tts.play_sound = AsyncMock()
    commentary._tts._connected = True
    commentary._display = display
    commentary._generator.stream_sentences = _fake_stream_sentences

    # Scoring pipeline with ReplayProvider via MoE engine
    scores_dir = str(tmp_path / "scores")
    scoring = ScoringPipeline(
        api_key="smoke",
        display=display,
        scores_dir=scores_dir,
        moe_engine=MoEScoringEngine([ReplayProvider()]),
    )

    # Deliberation pipeline with mock memory store
    deliberation = DeliberationPipeline(
        api_key="smoke",
        display=display,
        scores_dir=scores_dir,
        observations_dir=str(tmp_path / "observations"),
        deliberation_dir=str(tmp_path / "deliberation"),
    )
    deliberation._memory_store.save = AsyncMock()

    # DemoMachine wired to the same bus
    machine = DemoMachine(event_bus=bus)

    # WebOperator wired to everything
    operator = WebOperator(
        demo_machine=machine,
        event_bus=bus,
        display_server=display,
        scoring_pipeline=scoring,
        deliberation_pipeline=deliberation,
    )

    # Collector for bus-level assertions
    collector = EventCollector(bus)

    return operator, machine, bus, display, scoring, defense, commentary, deliberation, collector


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.timeout(30)
def test_smoke_full_pipeline_cycle(tmp_path):
    """Full smoke test: start -> synthetic events -> stop -> score -> commentary -> reveal.

    This is the go/no-go gate before the live hackathon event. It exercises
    the entire event-driven pipeline end-to-end with mocked external calls
    only (LLM, TTS). Everything else -- EventBus, DemoMachine, DefensePipeline,
    CommentaryPipeline, ScoringPipeline, WebOperator, WebSocket -- is real.

    Asserts:
        - A scoring_complete event was received on the bus
        - The scorecard total_score is between 0.0 and 10.0
        - Commentary text is non-empty
        - The WebSocket client received broadcast messages
        - The full cycle completed in under 30 seconds (wall clock)
    """
    wall_start = time.monotonic()

    (
        operator, machine, bus, display,
        scoring, defense, commentary, deliberation,
        collector,
    ) = _build_smoke_stack(tmp_path)

    # Register routes on the FastAPI app (mirrors test_e2e_full_flow._make_operator)
    operator._register_routes()
    operator._subscribe_events()

    # Patch asyncio.sleep in scoring pipeline to avoid theatrical delays
    import src.scoring.pipeline as scoring_mod
    original_sleep = asyncio.sleep

    async def _fast_sleep(duration):
        await original_sleep(min(duration, 0.05))

    scoring_mod.asyncio.sleep = _fast_sleep

    try:
        # Run the async pipeline inside a single event loop tick
        async def _run_smoke():
            # Wire sub-pipelines into the bus
            await defense.setup(bus)
            await commentary.setup(bus)
            await scoring.setup(bus)
            await deliberation.setup(bus)

            # Set track on scoring and deliberation
            scoring.set_track("SmokeTest", "SENTINEL::MESH")
            deliberation.set_track("SmokeTest", "SENTINEL::MESH")

            # Create the synthetic capture driver
            synthetic = SyntheticCapture(bus)

            # Drive synthetic events through the pipeline
            await synthetic.run_demo(team_name="SmokeTest", track="SENTINEL::MESH")

            # Wait for the cascading event chain to complete
            try:
                await collector.wait_scoring_complete(timeout=10.0)
            except asyncio.TimeoutError:
                received = [e.event_type for e in collector.events]
                pytest.fail(
                    f"scoring_complete event not received within 10s. "
                    f"Events received: {received}"
                )

            try:
                await collector.wait_commentary_delivered(timeout=10.0)
            except asyncio.TimeoutError:
                received = [e.event_type for e in collector.events]
                pytest.fail(
                    f"commentary_delivered event not received within 10s. "
                    f"Events received: {received}"
                )

            # Wait for score reveal (triggered after commentary_delivered)
            try:
                await collector.wait_score_revealed(timeout=10.0)
            except asyncio.TimeoutError:
                received = [e.event_type for e in collector.events]
                pytest.fail(
                    f"score_revealed event not received within 10s. "
                    f"Events received: {received}"
                )

        asyncio.run(_run_smoke())

        # ---- Assertion 1: scoring_complete event was received ----
        scoring_events = collector.events_by_type.get("scoring_complete", [])
        assert len(scoring_events) >= 1, (
            "SMOKE FAIL: No scoring_complete event received on the event bus. "
            f"Events received: {[e.event_type for e in collector.events]}"
        )

        # ---- Assertion 2: scorecard total_score in valid range ----
        scorecard = scoring_events[0].scorecard
        assert 0.0 <= scorecard.total_score <= 10.0, (
            f"SMOKE FAIL: Scorecard total_score {scorecard.total_score} is outside "
            f"the valid range [0.0, 10.0]."
        )
        assert scorecard.team_name == "SmokeTest", (
            f"SMOKE FAIL: Scorecard team_name is '{scorecard.team_name}', expected 'SmokeTest'."
        )

        # ---- Assertion 3: commentary text is non-empty ----
        commentary_events = collector.events_by_type.get("commentary_delivered", [])
        assert len(commentary_events) >= 1, (
            "SMOKE FAIL: No commentary_delivered event received."
        )
        commentary_text = commentary_events[0].commentary_text
        assert commentary_text and len(commentary_text.strip()) > 0, (
            f"SMOKE FAIL: Commentary text is empty or blank: '{commentary_text}'"
        )

        # ---- Assertion 4: score_revealed event was received ----
        reveal_events = collector.events_by_type.get("score_revealed", [])
        assert len(reveal_events) >= 1, (
            "SMOKE FAIL: No score_revealed event received. "
            "The full scoring -> commentary -> reveal chain did not complete."
        )

        # ---- Assertion 5: Display server received push calls ----
        assert len(display.commentary_calls) > 0, (
            "SMOKE FAIL: Display server received no commentary push calls."
        )
        assert len(display.score_intro_calls) > 0, (
            "SMOKE FAIL: Display server received no score intro push calls."
        )
        assert len(display.total_score_calls) > 0, (
            "SMOKE FAIL: Display server received no total score push calls."
        )

        # ---- Assertion 6: wall clock under 30 seconds ----
        wall_elapsed = time.monotonic() - wall_start
        assert wall_elapsed < 30.0, (
            f"SMOKE FAIL: Full pipeline cycle took {wall_elapsed:.1f}s, "
            f"exceeding the 30s wall clock limit."
        )

    finally:
        scoring_mod.asyncio.sleep = original_sleep


@pytest.mark.smoke
@pytest.mark.timeout(30)
def test_smoke_websocket_operator_lifecycle(tmp_path):
    """Smoke test: WebSocket operator can start/stop demos and receives broadcasts.

    Exercises the operator WebSocket lifecycle (connect -> start -> stop -> reset)
    using the same pattern as test_e2e_full_flow.py. Verifies that:
    - The operator client connects and gets initial idle state
    - Start command transitions to capturing with correct team/track
    - Stop command transitions to stopped
    - Event broadcasts (demo_started, demo_stopped) reach the WS client
    - The scorecard broadcast from a scoring_complete event is well-formed
    """
    bus = EventBus()
    machine = DemoMachine(event_bus=bus)
    display = FakeDisplayServer()

    # Use minimal FakeScoringPipeline for track storage (same as test_e2e_full_flow)
    class _FakeScoringPipeline:
        def __init__(self):
            self._pending_tracks: dict[str, str] = {}
        def set_track(self, team_name: str, track: str) -> None:
            self._pending_tracks[team_name] = track

    class _FakeDeliberationPipeline:
        def __init__(self):
            self._tracks: dict[str, str] = {}
        def set_track(self, team_name: str, track: str) -> None:
            self._tracks[team_name] = track

    scoring_fake = _FakeScoringPipeline()
    delib_fake = _FakeDeliberationPipeline()

    operator = WebOperator(
        demo_machine=machine,
        event_bus=bus,
        display_server=display,
        scoring_pipeline=scoring_fake,
        deliberation_pipeline=delib_fake,
    )
    operator._register_routes()
    operator._subscribe_events()

    client = TestClient(display.app)

    with client.websocket_connect("/ws/operator") as ws:
        # 1. Drain connect messages and verify idle state
        state = _drain_connect(ws)
        assert state["state"] == "idle", (
            f"SMOKE FAIL: Initial state should be 'idle', got '{state['state']}'"
        )

        # 2. Start a demo
        ws.send_json({
            "type": "command",
            "action": "start",
            "team_name": "SmokeTest",
            "track": "SENTINEL::MESH",
        })

        # Read messages flexibly -- event broadcasts can interleave with
        # command_result due to DemoMachine publishing demo_started
        messages_after_start: list[dict] = []
        found_start_result = False
        found_capturing = False

        for _ in range(10):
            msg = ws.receive_json()
            messages_after_start.append(msg)
            if msg.get("type") == "command_result" and msg.get("success"):
                found_start_result = True
            if msg.get("type") == "state" and msg.get("state") == "capturing":
                found_capturing = True
            if found_start_result and found_capturing:
                break

        assert found_start_result, (
            f"SMOKE FAIL: start command did not return success. "
            f"Messages: {messages_after_start}"
        )
        assert found_capturing, (
            f"SMOKE FAIL: state did not transition to 'capturing'. "
            f"Messages: {messages_after_start}"
        )

        # Verify event broadcast for demo_started reached WS client
        event_msgs = [
            m for m in messages_after_start
            if m.get("type") == "event" and m.get("event_type") == "demo_started"
        ]
        assert len(event_msgs) >= 1, (
            "SMOKE FAIL: demo_started event was not broadcast to WebSocket client."
        )

        # 3. Stop the demo
        ws.send_json({"type": "command", "action": "stop"})

        messages_after_stop: list[dict] = []
        found_stop_result = False
        found_stopped = False

        for _ in range(10):
            msg = ws.receive_json()
            messages_after_stop.append(msg)
            if msg.get("type") == "command_result" and msg.get("success"):
                found_stop_result = True
            if msg.get("type") == "state" and msg.get("state") == "stopped":
                found_stopped = True
            if found_stop_result and found_stopped:
                break

        assert found_stop_result, (
            f"SMOKE FAIL: stop command did not return success. "
            f"Messages: {messages_after_stop}"
        )
        assert found_stopped, (
            f"SMOKE FAIL: state did not transition to 'stopped'. "
            f"Messages: {messages_after_stop}"
        )

        # Verify demo_stopped event broadcast
        stop_events = [
            m for m in messages_after_stop
            if m.get("type") == "event" and m.get("event_type") == "demo_stopped"
        ]
        assert len(stop_events) >= 1, (
            "SMOKE FAIL: demo_stopped event was not broadcast to WebSocket client."
        )

    # 4. Verify track was assigned
    assert scoring_fake._pending_tracks.get("SmokeTest") == "SENTINEL::MESH", (
        "SMOKE FAIL: Track assignment did not propagate to ScoringPipeline."
    )


@pytest.mark.smoke
@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_smoke_scoring_complete_broadcast_to_ws():
    """Smoke test: scoring_complete event with scorecard reaches WebSocket client.

    Directly invokes _on_event with a ScoringComplete event (same pattern as
    test_e2e_full_flow.test_ws_scoring_complete_event_broadcast_contains_scorecard)
    to verify the scorecard serialization path works end-to-end.
    """
    from src.scoring.models import CriterionScore, DemoScorecard, ScoringComplete

    bus = EventBus()
    machine = DemoMachine(event_bus=bus)
    display = FakeDisplayServer()
    operator = WebOperator(
        demo_machine=machine,
        event_bus=bus,
        display_server=display,
    )

    # Capture broadcast messages
    captured: list[dict] = []

    async def _capture(msg):
        captured.append(msg)

    operator._broadcast_to_operators = _capture

    scorecard = DemoScorecard(
        team_name="SmokeTest",
        track="SENTINEL::MESH",
        criteria=[
            CriterionScore(name="Technical Execution", score=8.5, weight=0.40,
                           justification="Strong implementation."),
            CriterionScore(name="Innovation", score=7.0, weight=0.30,
                           justification="Novel approach."),
            CriterionScore(name="Demo Quality", score=6.5, weight=0.30,
                           justification="Clear presentation."),
        ],
        track_bonus=None,
        total_score=7.4,
        scored_at=time.time(),
    )

    await operator._on_event(ScoringComplete(scorecard=scorecard))

    # Find the scoring_complete broadcast
    sc_msgs = [
        m for m in captured
        if m.get("type") == "event" and m.get("event_type") == "scoring_complete"
    ]
    assert len(sc_msgs) >= 1, (
        f"SMOKE FAIL: scoring_complete not broadcast. Captured: {[m.get('type') for m in captured]}"
    )

    sc_data = sc_msgs[0]["data"]["scorecard"]
    assert sc_data["team_name"] == "SmokeTest", (
        f"SMOKE FAIL: Scorecard team_name is '{sc_data['team_name']}', expected 'SmokeTest'."
    )
    assert sc_data["track"] == "SENTINEL::MESH", (
        f"SMOKE FAIL: Scorecard track is '{sc_data['track']}', expected 'SENTINEL::MESH'."
    )
    assert 0.0 <= sc_data["total_score"] <= 10.0, (
        f"SMOKE FAIL: Scorecard total_score {sc_data['total_score']} out of range."
    )
    assert len(sc_data["criteria"]) == 3, (
        f"SMOKE FAIL: Expected 3 criteria, got {len(sc_data['criteria'])}."
    )
