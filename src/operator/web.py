"""WebSocket-based operator interface for remote demo control.

Provides a WebSocket endpoint on the FastAPI display server for bidirectional
operator commands and real-time event streaming. Designed for the React
operator dashboard at NEBULA:FOG 2026.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import TYPE_CHECKING

from fastapi import WebSocket, WebSocketDisconnect, Query, status
from statemachine.exceptions import TransitionNotAllowed

from src.capture.demo_machine import DemoMachine
from src.capture.event_bus import EventBus
from src.capture.models import CaptureEvent
from src.commentary.display_server import DisplayServer
from src.commentary.models import QARequested
from src.memory.models import DeliberationRequested
from src.operator.audit import log_command
from src.operator.cli import VALID_TRACKS

if TYPE_CHECKING:
    from src.memory.pipeline import DeliberationPipeline
    from src.scoring.pipeline import ScoringPipeline

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
        self._operator_connections: list[WebSocket] = []
        self._counters = {"frames": 0, "transcripts": 0, "attacks": 0, "clean": 0}
        self._send_lock = asyncio.Lock()
        self._demo_timer_task: asyncio.Task | None = None

    async def run(self) -> None:
        """Main operator loop: register routes, subscribe to events, and wait for quit.

        Blocks until the operator sends a quit command via WebSocket.
        """
        self._register_routes()
        self._subscribe_events()
        self._counter_task = asyncio.create_task(self._push_counters_loop())

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
            await ws.accept()
            self._operator_connections.append(ws)
            logger.info("Operator client connected (%d active)", len(self._operator_connections))

            # Push current state on connect
            await self._push_state(ws)

            try:
                while True:
                    data = await ws.receive_json()
                    await self._handle_command(data, ws)
            except WebSocketDisconnect:
                if ws in self._operator_connections:
                    self._operator_connections.remove(ws)
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
        self._demo_timer_task = asyncio.create_task(self._demo_timer_loop())

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
                    return

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
                await self._send_result(ws, True, f"Demo stopped for team: {team} (duration: {duration:.1f}s)")
                logger.info("Operator stopped demo for team: %s (%.1fs)", team, duration)
                log_command("stop", success=True, team_name=team, state_before=state_before, state_after=self._demo_machine.current_state.id, detail=f"duration={duration:.1f}s")

            elif action == "pause":
                session = self._demo_machine.current_session
                self._demo_machine.send("pause_demo")
                team = session.team_name if session else "Unknown"
                await self._send_result(ws, True, f"Demo paused for team: {team}")
                logger.info("Operator paused demo for team: %s", team)
                log_command("pause", success=True, team_name=team, state_before=state_before, state_after=self._demo_machine.current_state.id)

            elif action == "resume":
                session = self._demo_machine.current_session
                self._demo_machine.send("resume_demo")
                team = session.team_name if session else "Unknown"
                await self._send_result(ws, True, f"Demo resumed for team: {team}")
                logger.info("Operator resumed demo for team: %s", team)
                log_command("resume", success=True, team_name=team, state_before=state_before, state_after=self._demo_machine.current_state.id)

            elif action == "reset":
                self._cancel_demo_timer()
                self._demo_machine.send("reset")
                await self._send_result(ws, True, "Ready for next demo.")
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

                asyncio.create_task(_run_rehearsal())
                logger.info("Operator triggered rehearsal mode from dashboard")
                log_command("rehearsal", success=True, state_before=state_before, state_after=self._demo_machine.current_state.id)

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
                pass

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
            track = self._scoring_pipeline._pending_tracks.get(team_name, "")

        state_data = {
            "type": "state",
            "state": state_id,
            "team_name": team_name,
            "track": track,
            "started_at": session.started_at if session else None,
        }

        return state_data

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
                if ws is not None and ws in self._operator_connections:
                    self._operator_connections.remove(ws)
