"""WebSocket-based operator interface for remote demo control.

Provides a WebSocket endpoint on the FastAPI display server for bidirectional
operator commands and real-time event streaming. Designed for the React
operator dashboard at NEBULA:FOG 2026.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import Query, WebSocket, WebSocketDisconnect, status
from statemachine.exceptions import TransitionNotAllowed

from src.capture.demo_machine import DemoMachine
from src.capture.event_bus import EventBus
from src.capture.models import CaptureEvent
from src.commentary.display_server import DisplayServer
from src.commentary.models import QARequested
from src.config.tracks import VALID_TRACKS
from src.memory.models import DeliberationRequested
from src.operator.audit import log_command
from src.resilience.metrics import default_metrics

if TYPE_CHECKING:
    from src.memory.pipeline import DeliberationPipeline
    from src.scoring.pipeline import ScoringPipeline

# Feature A: Path to session checkpoint file
_CHECKPOINT_PATH = Path("data/session_checkpoint.json")

logger = logging.getLogger(__name__)

# Default 10 minutes, configurable via environment variable (seconds)
MAX_DEMO_DURATION = float(os.environ.get("MAX_DEMO_DURATION", "600"))
# Warning fires at 90% of max duration
_WARNING_RATIO = 0.9


class WebOperator:
    """WebSocket-based operator interface for remote demo control.

    Registers routes on the display server's FastAPI app to serve the operator
    dashboard and handle bidirectional WebSocket communication. Mirrors the
    command handling logic from OperatorCLI but uses JSON messages instead of
    stdin text commands.

    Args:
        demo_machine: The DemoMachine instance controlling demo lifecycle.
        event_bus: Event bus for subscribing to capture events.
        display_server: The DisplayServer instance with the FastAPI app.
        scoring_pipeline: Optional scoring pipeline for track assignment.
        deliberation_pipeline: Optional deliberation pipeline.
    """

    def __init__(
        self,
        demo_machine: DemoMachine,
        event_bus: EventBus,
        display_server: DisplayServer,
        scoring_pipeline: ScoringPipeline | None = None,
        deliberation_pipeline: DeliberationPipeline | None = None,
    ) -> None:
        self._demo_machine = demo_machine
        self._event_bus = event_bus
        self._display_server = display_server
        self._scoring_pipeline = scoring_pipeline
        self._deliberation_pipeline = deliberation_pipeline

        self._quit_signal = asyncio.Event()
        self._operator_connections: set[WebSocket] = set()
        self._counters = {"frames": 0, "transcripts": 0, "attacks": 0, "clean": 0}
        self._total_injections: int = 0
        self._send_lock = asyncio.Lock()
        self._demo_timer_task: asyncio.Task | None = None
        self._scoring_phase: str | None = None

    async def run(self) -> None:
        """Main operator loop: register routes, subscribe to events, and wait for quit.

        Blocks until the operator sends a quit command via WebSocket.
        """
        # Feature A: Ensure data/ directory exists and check for incomplete checkpoint
        _CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if _CHECKPOINT_PATH.exists():
            try:
                raw = await asyncio.to_thread(_CHECKPOINT_PATH.read_text)
                chk = json.loads(raw)
                if chk.get("state") != "idle":
                    team_name = chk.get("team_name", "unknown")
                    logger.warning(
                        "Found incomplete session checkpoint for %s — manual recovery may be needed",
                        team_name,
                    )
            except Exception:
                logger.debug("Could not read session checkpoint on startup", exc_info=True)

        self._register_routes()
        self._subscribe_events()
        self._counter_task = asyncio.create_task(self._push_counters_loop(), name="push-counters")

        logger.info("WebOperator started, waiting for commands via WebSocket")
        try:
            await self._quit_signal.wait()
        except asyncio.CancelledError:
            pass
        logger.info("WebOperator shutting down")

        # Cancel background tasks on shutdown
        self._cancel_demo_timer()
        if self._counter_task and not self._counter_task.done():
            self._counter_task.cancel()
            try:
                await self._counter_task
            except asyncio.CancelledError:
                pass

    def _register_routes(self) -> None:
        """Register HTTP and WebSocket routes on the display server's FastAPI app."""
        app = self._display_server.app

        @app.get("/api/health")
        async def health_endpoint():
            from src.resilience.health import default_health

            status = default_health.get_status()
            return {
                "status": "ok" if all(status.values()) or not status else "degraded",
                "services": status,
            }

        @app.get("/api/metrics")
        async def metrics_endpoint(format: str = Query("json", alias="format")):
            from src.resilience.metrics import default_metrics

            if format.lower() == "prometheus":
                from fastapi.responses import PlainTextResponse
                return PlainTextResponse(
                    default_metrics.prometheus_text(),
                    media_type="text/plain; charset=utf-8",
                )
            return default_metrics.snapshot()

        @app.get("/api/report-card/{team_name}")
        async def report_card_endpoint(team_name: str):
            from fastapi.responses import HTMLResponse

            from src.reports.card import generate_report_card_html

            html = await generate_report_card_html(team_name)
            if html is None:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=404,
                    content={"error": f"No scorecard found for team '{team_name}'"},
                )
            return HTMLResponse(html)

        @app.get("/api/report-cards")
        async def report_cards_list():
            from src.scoring.store import ScoreStore
            score_store = ScoreStore(scores_dir="data/scores")
            scorecards = await score_store.load_all()
            return [
                {"team_name": sc.team_name, "track": sc.track, "total_score": sc.total_score}
                for sc in sorted(scorecards, key=lambda s: s.total_score, reverse=True)
            ]

        @app.post("/api/human-score")
        async def submit_human_score(score: dict, token: str = Query(default="")):
            """Submit a human judge's score for a team (requires operator token)."""
            import time as _time

            from fastapi.responses import JSONResponse

            from src.scoring.human import HumanScore, HumanScoreStore

            required_token = os.environ.get("OPERATOR_TOKEN", "")
            if required_token and token != required_token:
                return JSONResponse(status_code=403, content={"error": "Forbidden"})

            try:
                human_score = HumanScore(
                    judge_name=score.get("judge_name", ""),
                    team_name=score.get("team_name", ""),
                    total_score=score.get("total_score", 0),
                    notes=score.get("notes", ""),
                    submitted_at=_time.time(),
                )
            except Exception as e:
                return JSONResponse(status_code=400, content={"error": str(e)})

            if not human_score.judge_name or not human_score.team_name:
                return JSONResponse(status_code=400, content={"error": "judge_name and team_name are required"})

            store = HumanScoreStore()
            await store.save(human_score)
            return {"status": "ok", "team_name": human_score.team_name, "judge": human_score.judge_name}

        @app.get("/api/blended-score/{team_name}")
        async def blended_score_endpoint(team_name: str):
            """Get blended AI + human score for a team."""
            from fastapi.responses import JSONResponse

            from src.scoring.human import blend_scores

            result = await blend_scores(team_name)
            if result is None:
                return JSONResponse(status_code=404, content={"error": f"No AI scorecard found for '{team_name}'"})
            return result.model_dump()

        @app.get("/api/blended-scores")
        async def blended_scores_list():
            """Get blended scores for all teams."""
            from src.scoring.human import blend_scores
            from src.scoring.store import ScoreStore

            score_store = ScoreStore(scores_dir="data/scores")
            scorecards = await score_store.load_all()
            results = []
            for sc in scorecards:
                blended = await blend_scores(sc.team_name)
                if blended:
                    results.append({
                        "team_name": blended.team_name,
                        "track": blended.track,
                        "ai_score": blended.ai_score,
                        "human_score": blended.human_score,
                        "blended_score": blended.blended_score,
                        "human_judge_count": len(blended.human_judges),
                    })
            return sorted(results, key=lambda r: r["blended_score"], reverse=True)

        @app.get("/api/export")
        async def export_all(
            include_audit: bool = Query(default=False),
            include_observations: bool = Query(default=True),
            include_events: bool = Query(default=False),
        ):
            """Export all event data as JSON."""
            from src.reports.export import export_event_data
            result = await export_event_data(
                include_audit=include_audit,
                include_observations=include_observations,
                include_events=include_events,
            )
            return result.model_dump()

        @app.get("/api/export/{team_name}")
        async def export_team(team_name: str):
            """Export all data for a single team."""
            from fastapi.responses import JSONResponse

            from src.reports.export import export_team_data
            result = await export_team_data(team_name)
            if result is None:
                return JSONResponse(status_code=404, content={"error": f"No data found for team '{team_name}'"})
            return result.model_dump()

        @app.websocket("/ws/operator")
        async def operator_ws(ws: WebSocket, token: str = Query(default="")) -> None:
            required_token = os.environ.get("OPERATOR_TOKEN", "")
            if required_token and token != required_token:
                logger.warning(
                    "Operator WebSocket rejected: invalid token (origin: %s)",
                    ws.headers.get("origin", "unknown"),
                )
                await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
                return
            max_operator = int(os.environ.get("MAX_OPERATOR_CONNECTIONS", "10"))
            if len(self._operator_connections) >= max_operator:
                logger.warning("Operator connection cap reached (%d), rejecting", max_operator)
                await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Too many connections")
                return
            await ws.accept()
            self._operator_connections.add(ws)
            logger.info("Operator client connected (%d active)", len(self._operator_connections))

            # Push current state on connect
            await self._push_state(ws)

            try:
                while True:
                    # Wait for a command or pong; send ping after 10s of silence
                    try:
                        data = await asyncio.wait_for(ws.receive_json(), timeout=10.0)
                        if data.get("type") != "pong":
                            await self._handle_command(data, ws)
                    except asyncio.TimeoutError:
                        # No message received — send ping to probe the connection
                        try:
                            await ws.send_json({"type": "ping"})
                        except Exception:
                            break
                        # Wait for any response with a 15-second deadline
                        try:
                            await asyncio.wait_for(ws.receive_json(), timeout=15.0)
                        except asyncio.TimeoutError:
                            logger.info("Operator client heartbeat timeout, closing")
                            break
            except WebSocketDisconnect:
                pass
            finally:
                self._operator_connections.discard(ws)
                logger.info("Operator client disconnected (%d active)", len(self._operator_connections))

    def _subscribe_events(self) -> None:
        """Subscribe to all capture events for real-time streaming to operator clients."""
        # Subscribe to all events and broadcast to operator clients
        self._event_bus.subscribe_all(self._on_event)

    async def _on_event(self, event: CaptureEvent) -> None:
        """Handle incoming capture events: update counters and broadcast to operator clients.

        Args:
            event: The capture event to process.
        """
        # Update counters based on event type
        if event.event_type == "key_frame_detected":
            self._counters["frames"] += 1
        elif event.event_type == "transcript_received":
            self._counters["transcripts"] += 1
        elif event.event_type == "injection_detected":
            self._counters["attacks"] += 1
            # Feature C: Broadcast injection blocked notification to audience display
            # Only show during active capture — don't overwrite score reveal
            if (
                hasattr(event, "attempt")
                and self._demo_machine.current_state.id == "capturing"
            ):
                attempt = event.attempt
                category = getattr(attempt, "pattern", "injection_attempt")
                confidence = getattr(attempt, "confidence", "medium")
                team_name = getattr(attempt, "team_name", "")
                asyncio.create_task(
                    self._display_server.push_injection_blocked(
                        category=category,
                        confidence=confidence,
                        roast="",
                        team_name=team_name,
                    ),
                    name="push-injection-blocked",
                )
        elif event.event_type == "observation_verified":
            # Count clean observations
            if hasattr(event, "output") and hasattr(event.output, "observations"):
                self._counters["clean"] += len(event.output.observations)

        # Serialize and broadcast event to operator clients
        event_data = {
            "type": "event",
            "event_type": event.event_type,
            "timestamp": event.timestamp,
            "data": {},
        }

        # Add relevant payload fields based on event type
        if hasattr(event, "team_name"):
            event_data["data"]["team_name"] = event.team_name
        if hasattr(event, "commentary_text"):
            event_data["data"]["text"] = event.commentary_text
        if hasattr(event, "segment"):
            event_data["data"]["segment"] = event.segment
        if hasattr(event, "attempt"):
            event_data["data"]["attempt"] = {
                "injection_type": event.attempt.injection_type,
                "pattern": event.attempt.pattern,
                "confidence": event.attempt.confidence,
            }

        # Extract full scorecard from scoring_complete events
        if event.event_type == "scoring_complete" and hasattr(event, "scorecard"):
            sc = event.scorecard
            event_data["data"]["scorecard"] = {
                "team_name": sc.team_name,
                "track": sc.track,
                "total_score": sc.total_score,
                "is_fallback": sc.is_fallback,
                "criteria": [
                    {"name": c.name, "score": c.score, "weight": c.weight, "justification": c.justification}
                    for c in sc.criteria
                ],
                "track_bonus": {
                    "name": sc.track_bonus.name,
                    "score": sc.track_bonus.score,
                    "weight": sc.track_bonus.weight,
                    "justification": sc.track_bonus.justification,
                } if sc.track_bonus else None,
            }

        await self._broadcast_to_operators(event_data)

        # Push authoritative scoring phase based on pipeline events
        if event.event_type == "demo_stopped":
            await self._push_scoring_phase("sanitizing")
        elif event.event_type == "observation_verified":
            await self._push_scoring_phase("scoring")
        elif event.event_type == "scoring_complete":
            await self._push_scoring_phase("revealing")
        elif event.event_type == "scoring_failed":
            await self._push_scoring_phase("failed")
        elif event.event_type == "demo_started":
            await self._push_scoring_phase(None)

    async def _push_counters_loop(self) -> None:
        """Background task that pushes counter and health updates to operator clients every second."""
        while True:
            await asyncio.sleep(1.0)
            await self._broadcast_to_operators({
                "type": "counters",
                **self._counters,
            })

            # Also push health status on the same 1s interval
            from src.resilience.health import default_health

            health_status = default_health.get_status()
            await self._broadcast_to_operators({
                "type": "health",
                "services": health_status,
            })

    def _start_demo_timer(self) -> None:
        """Start a background timer that warns operators as demo approaches max duration."""
        self._cancel_demo_timer()
        self._demo_timer_task = asyncio.create_task(self._demo_timer_loop(), name="demo-timer")

    def _cancel_demo_timer(self) -> None:
        """Cancel the running demo timer if any."""
        if self._demo_timer_task and not self._demo_timer_task.done():
            self._demo_timer_task.cancel()
        self._demo_timer_task = None

    async def _demo_timer_loop(self) -> None:
        """Background loop that sends time warnings to operator clients.

        At 90% of MAX_DEMO_DURATION, sends a warning alert.
        At 100%, sends a critical overtime alert.
        """
        warning_sent = False
        overtime_sent = False
        warning_threshold = MAX_DEMO_DURATION * _WARNING_RATIO

        try:
            while True:
                await asyncio.sleep(5.0)
                session = self._demo_machine.current_session
                if session is None or session.started_at is None:
                    continue

                elapsed = time.time() - session.started_at
                remaining = MAX_DEMO_DURATION - elapsed

                if elapsed >= warning_threshold and not warning_sent:
                    warning_sent = True
                    await self._broadcast_to_operators({
                        "type": "demo_timer",
                        "level": "warning",
                        "message": f"Demo approaching time limit ({int(remaining)}s remaining)",
                        "elapsed": round(elapsed, 1),
                        "max_duration": MAX_DEMO_DURATION,
                    })
                    logger.warning(
                        "Demo timer warning: %.0fs elapsed, %.0fs remaining (max %.0fs)",
                        elapsed, remaining, MAX_DEMO_DURATION,
                    )

                if elapsed >= MAX_DEMO_DURATION and not overtime_sent:
                    overtime_sent = True
                    await self._broadcast_to_operators({
                        "type": "demo_timer",
                        "level": "critical",
                        "message": "Demo has exceeded maximum duration",
                        "elapsed": round(elapsed, 1),
                        "max_duration": MAX_DEMO_DURATION,
                    })
                    logger.warning(
                        "Demo timer critical: demo exceeded max duration of %.0fs",
                        MAX_DEMO_DURATION,
                    )
                    # Auto-stop: prevent capture from running indefinitely
                    try:
                        self._demo_machine.send("stop_demo")
                        logger.warning("Demo auto-stopped after exceeding max duration")
                    except Exception:
                        logger.warning(
                            "Could not auto-stop demo (may already be stopping)",
                            exc_info=True,
                        )
                    return

        except asyncio.CancelledError:
            pass

    async def _handle_command(self, data: dict, ws: WebSocket) -> None:
        """Handle a command from the operator client.

        Args:
            data: JSON command data with 'action' field.
            ws: The WebSocket connection that sent the command.
        """
        action = data.get("action", "")
        default_metrics.inc("operator_commands_total")
        state_before = self._demo_machine.current_state.id

        try:
            if action == "start":
                team_name = data.get("team_name", "")
                track = data.get("track")

                if not team_name:
                    await self._send_result(ws, False, "Team name required")
                    return

                # Handle track assignment (same logic as OperatorCLI)
                if track and self._scoring_pipeline:
                    if track in VALID_TRACKS:
                        self._scoring_pipeline.set_track(team_name, track)
                        if self._deliberation_pipeline:
                            self._deliberation_pipeline.set_track(team_name, track)
                        logger.info("Track %s assigned to team %s", track, team_name)
                    else:
                        await self._send_result(
                            ws, True, f"Warning: Unknown track '{track}'. Demo will start but scoring will use default track ROGUE::AGENT."
                        )
                elif not track:
                    logger.info("No track specified -- defaulting to ROGUE::AGENT for scoring")

                # Reset counters on demo start
                self._counters = {"frames": 0, "transcripts": 0, "attacks": 0, "clean": 0}

                self._demo_machine.send("start_demo", team_name=team_name)
                self._start_demo_timer()

                # Feature A: Write checkpoint after start transition
                await self._write_checkpoint(self._demo_machine.current_state.id)

                # Feature E: Broadcast capture_started to audience display
                resolved_track = track or (
                    self._scoring_pipeline.get_track(team_name)
                    if self._scoring_pipeline else ""
                )
                await self._display_server.clear()
                await self._display_server.push_capture_started(
                    team_name=team_name, track=resolved_track,
                )

                await self._send_result(ws, True, f"Demo started for {team_name}")
                logger.info("Operator started demo for team: %s", team_name)
                log_command("start", success=True, team_name=team_name, track=track or "", state_before=state_before, state_after=self._demo_machine.current_state.id)

            elif action == "stop":
                self._cancel_demo_timer()
                session = self._demo_machine.current_session
                self._demo_machine.send("stop_demo")
                duration = 0.0
                if session and session.started_at:
                    duration = time.time() - session.started_at
                team = session.team_name if session else "Unknown"
                # Feature A: Write checkpoint after stop transition
                await self._write_checkpoint(self._demo_machine.current_state.id)
                await self._send_result(ws, True, f"Demo stopped for team: {team} (duration: {duration:.1f}s)")
                logger.info("Operator stopped demo for team: %s (%.1fs)", team, duration)
                log_command("stop", success=True, team_name=team, state_before=state_before, state_after=self._demo_machine.current_state.id, detail=f"duration={duration:.1f}s")

            elif action == "pause":
                session = self._demo_machine.current_session
                self._demo_machine.send("pause_demo")
                team = session.team_name if session else "Unknown"
                # Feature A: Write checkpoint after pause transition
                await self._write_checkpoint(self._demo_machine.current_state.id)
                await self._send_result(ws, True, f"Demo paused for team: {team}")
                logger.info("Operator paused demo for team: %s", team)
                log_command("pause", success=True, team_name=team, state_before=state_before, state_after=self._demo_machine.current_state.id)

            elif action == "resume":
                session = self._demo_machine.current_session
                self._demo_machine.send("resume_demo")
                team = session.team_name if session else "Unknown"
                # Feature A: Write checkpoint after resume transition
                await self._write_checkpoint(self._demo_machine.current_state.id)
                await self._send_result(ws, True, f"Demo resumed for team: {team}")
                logger.info("Operator resumed demo for team: %s", team)
                log_command("resume", success=True, team_name=team, state_before=state_before, state_after=self._demo_machine.current_state.id)

            elif action == "reset":
                self._cancel_demo_timer()

                # Cancel any in-flight score reveal before transitioning
                if self._scoring_pipeline is not None:
                    self._scoring_pipeline.cancel_reveal()
                await self._display_server.clear()

                self._demo_machine.send("reset")

                # Feature A: Delete checkpoint when session completes (state → idle)
                await self._delete_checkpoint()

                # Feature F: Load leaderboard from ScoreStore and broadcast intermission
                try:
                    from src.scoring.store import ScoreStore

                    score_store = ScoreStore(scores_dir="data/scores")
                    scorecards = await score_store.load_all()
                    leaderboard = [
                        {
                            "team_name": sc.team_name,
                            "total_score": sc.total_score,
                            "track": sc.track,
                        }
                        for sc in sorted(scorecards, key=lambda s: s.total_score, reverse=True)
                    ]
                    self._total_injections += self._counters.get("attacks", 0)
                    await self._display_server.push_intermission(leaderboard, self._total_injections)
                except Exception:
                    logger.warning("Failed to push intermission leaderboard", exc_info=True)

                await self._send_result(ws, True, "Ready for next demo.")
                await self._push_scoring_phase(None)
                logger.info("Operator reset demo machine")
                log_command("reset", success=True, state_before=state_before, state_after=self._demo_machine.current_state.id)

            elif action == "qa":
                state_id = self._demo_machine.current_state.id
                if state_id != "stopped":
                    await self._send_result(ws, False, f"Q&A only available after demo stops (current state: '{state_id}').")
                    return

                session = self._demo_machine.current_session
                team_name = session.team_name if session else "Unknown"
                self._event_bus.publish(QARequested(team_name=team_name))
                await self._send_result(ws, True, f"Q&A mode activated for team: {team_name}")
                logger.info("Operator triggered Q&A for team: %s", team_name)
                log_command("qa", success=True, team_name=team_name, state_before=state_before, state_after=self._demo_machine.current_state.id)

            elif action == "deliberate":
                self._event_bus.publish(DeliberationRequested())
                await self._send_result(ws, True, "Deliberation triggered. Processing all demos...")
                logger.info("Operator triggered end-of-event deliberation")
                log_command("deliberate", success=True, state_before=state_before, state_after=self._demo_machine.current_state.id)

            elif action == "rehearsal":
                from src.rehearsal import RehearsalPipeline

                await self._send_result(ws, True, "Starting rehearsal mode...")
                rehearsal = RehearsalPipeline(display=self._display_server)

                async def _run_rehearsal():
                    try:
                        await rehearsal.run_demo()
                        logger.info("Dashboard-triggered rehearsal complete")
                    except Exception:
                        logger.exception("Rehearsal failed")

                asyncio.create_task(_run_rehearsal(), name="rehearsal")
                logger.info("Operator triggered rehearsal mode from dashboard")
                log_command("rehearsal", success=True, state_before=state_before, state_after=self._demo_machine.current_state.id)

            elif action == "get_state":
                # Client-initiated state resync (e.g. after reconnect)
                await self._push_state(ws)
                return

            elif action == "quit":
                await self._send_result(ws, True, "Shutting down")
                self._quit_signal.set()

            else:
                await self._send_result(ws, False, f"Unknown command: '{action}'")
                log_command(action, success=False, state_before=state_before, state_after=state_before, detail="unknown command")
                return

        except TransitionNotAllowed:
            state_id = self._demo_machine.current_state.id
            await self._send_result(ws, False, f"Cannot '{action}' in state '{state_id}'")
            log_command(action, success=False, state_before=state_before, state_after=state_id, detail=f"transition not allowed from '{state_before}'")
        except Exception:
            logger.exception("Unhandled exception in command handler for '%s'", action)
            await self._send_result(ws, False, f"Internal error processing '{action}'")

        # Push updated state to ALL operator clients after command
        await self._broadcast_state()

    async def _send_result(self, ws: WebSocket, success: bool, message: str) -> None:
        """Send a command result to a specific operator client.

        Args:
            ws: The WebSocket connection to send to.
            success: Whether the command succeeded.
            message: Result message.
        """
        async with self._send_lock:
            try:
                await asyncio.wait_for(ws.send_json({
                    "type": "command_result",
                    "success": success,
                    "message": message,
                }), timeout=5.0)
            except Exception:
                logger.warning(
                    "Failed to send command result to operator (success=%s, message=%s)",
                    success, message[:100],
                    exc_info=True,
                )

    async def _push_scoring_phase(self, phase: str | None) -> None:
        """Broadcast a scoring_phase message to all operator clients.

        Args:
            phase: The new phase value, or None to clear.
        """
        self._scoring_phase = phase
        await self._broadcast_to_operators({"type": "scoring_phase", "phase": phase})

    async def _push_state(self, ws: WebSocket) -> None:
        """Push current demo state and health to a specific operator client.

        Args:
            ws: The WebSocket connection to send to.
        """
        state_data = self._get_state_data()
        async with self._send_lock:
            try:
                await asyncio.wait_for(ws.send_json(state_data), timeout=5.0)

                from src.resilience.health import default_health

                health_status = default_health.get_status()
                await asyncio.wait_for(ws.send_json({
                    "type": "health",
                    "services": health_status,
                }), timeout=5.0)

                # Send current scoring phase so reconnecting clients restore the right phase
                await asyncio.wait_for(ws.send_json({
                    "type": "scoring_phase",
                    "phase": self._scoring_phase,
                }), timeout=5.0)
            except Exception:
                pass

    async def _broadcast_state(self) -> None:
        """Broadcast current demo state to all connected operator clients."""
        state_data = self._get_state_data()
        await self._broadcast_to_operators(state_data)

    def _get_state_data(self) -> dict:
        """Get current demo state as a JSON-serializable dict.

        Returns:
            Dict with state, team_name, track, and started_at fields.
        """
        session = self._demo_machine.current_session
        state_id = self._demo_machine.current_state.id

        team_name = session.team_name if session else ""
        track = ""
        if team_name and self._scoring_pipeline:
            track = self._scoring_pipeline.get_track(team_name)

        state_data = {
            "type": "state",
            "state": state_id,
            "team_name": team_name,
            "track": track,
            "started_at": session.started_at if session else None,
        }

        return state_data

    async def _write_checkpoint(self, state_id: str) -> None:
        """Write current session state to the crash-recovery checkpoint file.

        Feature A: Called after every state transition. Uses asyncio.to_thread
        to avoid blocking the event loop during file I/O.
        """
        session = self._demo_machine.current_session
        team_name = session.team_name if session else ""
        track = ""
        if team_name and self._scoring_pipeline:
            track = self._scoring_pipeline.get_track(team_name)

        checkpoint = {
            "team_name": team_name,
            "track": track,
            "state": state_id,
            "started_at": session.started_at if session else None,
            "observation_count": self._counters.get("clean", 0),
            "timestamp": time.time(),
        }
        try:
            data = json.dumps(checkpoint)
            await asyncio.to_thread(_CHECKPOINT_PATH.write_text, data)
        except Exception:
            logger.debug("Failed to write session checkpoint", exc_info=True)

    async def _delete_checkpoint(self) -> None:
        """Delete the checkpoint file when session completes (state → idle).

        Feature A: Removes the checkpoint so a clean startup doesn't warn.
        """
        try:
            await asyncio.to_thread(_CHECKPOINT_PATH.unlink, True)
        except Exception:
            logger.debug("Failed to delete session checkpoint", exc_info=True)

    async def _broadcast_to_operators(self, message: dict) -> None:
        """Broadcast a message to all connected operator clients.

        Uses a lock to prevent concurrent send_json calls on the same WebSocket
        from interleaving frames. Sends to all clients concurrently within the
        lock so a slow client doesn't delay delivery to responsive ones.

        Args:
            message: JSON-serializable message dict.
        """
        if not self._operator_connections:
            return

        async def _safe_send(ws: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(ws.send_json(message), timeout=5.0)
                return None
            except Exception:
                return ws

        async with self._send_lock:
            results = await asyncio.gather(
                *[_safe_send(ws) for ws in self._operator_connections]
            )

            # Clean up disconnected/timed-out clients
            for ws in results:
                if ws is not None:
                    self._operator_connections.discard(ws)
