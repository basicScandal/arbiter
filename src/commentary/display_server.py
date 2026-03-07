"""FastAPI display server with WebSocket broadcast for audience text display.

Runs an async web server that pushes commentary and Q&A text to connected
browser clients via WebSocket. Designed for projection on a large screen
at NEBULA:FOG 2026.
"""

from __future__ import annotations

import asyncio
import atexit
import json
import logging
import os
import signal
import socket
import subprocess
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


class ConnectionManager:
    """Manage active WebSocket connections and broadcast messages."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []
        self._broadcast_lock = asyncio.Lock()
        # Feature B: State cache for replaying current screen state to new clients
        self._last_screen_state: dict | None = None
        self._criteria_sequence: list[dict] = []

    async def connect(self, ws: WebSocket) -> None:
        """Accept and register a new WebSocket connection.

        After accepting, replays the current screen state so the new client
        sees the same thing as existing connected clients (Feature B).
        """
        await ws.accept()
        self.active.append(ws)
        logger.info("Display client connected (%d active)", len(self.active))

        # Feature B: Replay cached state to the newly connected client
        if self._last_screen_state:
            try:
                await ws.send_json(self._last_screen_state)
                if self._last_screen_state.get("type") == "score_intro":
                    for criterion in self._criteria_sequence:
                        await ws.send_json(criterion)
            except Exception:
                logger.debug("Failed to replay state to new display client", exc_info=True)

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        if ws in self.active:
            self.active.remove(ws)
        logger.info("Display client disconnected (%d active)", len(self.active))

    async def replay_state(self, ws: WebSocket) -> None:
        """Re-send cached screen state to a specific client (e.g. on request_state)."""
        if self._last_screen_state:
            try:
                await ws.send_json(self._last_screen_state)
                if self._last_screen_state.get("type") == "score_intro":
                    for criterion in self._criteria_sequence:
                        await ws.send_json(criterion)
            except Exception:
                logger.debug("Failed to replay state on request", exc_info=True)

    async def broadcast(self, message: dict) -> None:
        """Send a JSON message to all connected clients.

        Updates the screen state cache before broadcasting so new clients
        connecting later can be replayed the current state (Feature B).
        Uses a lock to prevent concurrent broadcasts from interleaving
        WebSocket frames. Silently removes clients that have disconnected.
        """
        # Feature B: Update cached screen state based on message type
        msg_type = message.get("type")
        if msg_type == "clear":
            self._last_screen_state = None
            self._criteria_sequence = []
        elif msg_type == "score_intro":
            self._last_screen_state = message
            self._criteria_sequence = []
        elif msg_type == "score_criterion":
            self._criteria_sequence.append(message)
        elif msg_type in (
            "deliberation_ranking",
            "deliberation_narrative",
            "commentary",
            "question",
            "capture_started",
            "intermission",
            "injection_blocked",
        ):
            self._last_screen_state = message

        async with self._broadcast_lock:
            disconnected: list[WebSocket] = []
            for ws in self.active:
                try:
                    await ws.send_json(message)
                except Exception:
                    disconnected.append(ws)
            for ws in disconnected:
                self.disconnect(ws)


class DisplayServer:
    """Async display server pushing commentary to browser clients.

    Runs FastAPI with uvicorn as a background asyncio task. WebSocket
    endpoint broadcasts JSON messages to all connected display clients.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        self._host = host
        self._port = port
        self._app = FastAPI(title="Arbiter Display")
        self._manager = ConnectionManager()
        self._templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
        self._server: uvicorn.Server | None = None
        self._serve_task: asyncio.Task | None = None

        self._register_routes()

    @property
    def app(self) -> FastAPI:
        """Expose the FastAPI app for external route registration (e.g., WebOperator)."""
        return self._app

    def _register_routes(self) -> None:
        """Register HTTP and WebSocket routes on the FastAPI app."""

        @self._app.get("/", response_class=HTMLResponse)
        async def display_page(request: Request) -> HTMLResponse:
            return self._templates.TemplateResponse(request, "display.html")

        @self._app.get("/stream", response_class=HTMLResponse)
        async def stream_overlay(request: Request) -> HTMLResponse:
            return self._templates.TemplateResponse(request, "stream.html")

        # Mount React audience display (production build)
        react_dist = Path(__file__).parent / "../../audience-display/dist"
        if react_dist.exists():
            self._app.mount(
                "/app",
                StaticFiles(directory=str(react_dist.resolve()), html=True),
                name="react-app",
            )

        # Mount operator dashboard (production build)
        operator_dist = Path(__file__).parent / "../../operator-dashboard/dist"
        if operator_dist.exists():
            self._app.mount(
                "/operator",
                StaticFiles(directory=str(operator_dist.resolve()), html=True),
                name="operator-app",
            )

        # Mount public static files (criteria pages, etc.)
        public_dir = Path(__file__).parent / "../../public"
        if public_dir.exists():
            self._app.mount(
                "/public",
                StaticFiles(directory=str(public_dir.resolve()), html=True),
                name="public-static",
            )

        @self._app.websocket("/ws/display")
        async def websocket_endpoint(ws: WebSocket) -> None:
            await self._manager.connect(ws)
            try:
                while True:
                    # Send ping to detect silent disconnections
                    try:
                        await ws.send_json({"type": "ping"})
                    except Exception:
                        break
                    # Wait for any response (pong, request_state, etc.) with timeout
                    try:
                        raw = await asyncio.wait_for(ws.receive_text(), timeout=15.0)
                        try:
                            data = json.loads(raw)
                            if data.get("type") == "request_state":
                                # Client-initiated state resync (e.g. after reconnect)
                                await self._manager.replay_state(ws)
                        except (json.JSONDecodeError, TypeError):
                            pass
                    except asyncio.TimeoutError:
                        logger.info("Display client heartbeat timeout, closing")
                        break
            except WebSocketDisconnect:
                pass
            finally:
                self._manager.disconnect(ws)

    async def start(self) -> None:
        """Start uvicorn as a non-blocking asyncio task.

        Kills any stale process holding the port before binding, and registers
        an atexit handler to ensure the socket is released on unclean exit.

        Raises:
            RuntimeError: If the port is still in use after cleanup or uvicorn
                fails to bind. Callers should catch this and mark health as
                unhealthy rather than crashing the pipeline.
        """
        self._free_port(self._port)

        # Pre-validate: if port is still occupied after cleanup, fail loudly
        if not self._port_is_free(self._port):
            raise RuntimeError(
                f"Display server cannot start — port {self._port} is already in use. "
                f"Check for other processes with: lsof -i :{self._port}"
            )

        config = uvicorn.Config(
            app=self._app,
            host=self._host,
            port=self._port,
            log_level="warning",
        )
        self._server = uvicorn.Server(config)
        self._serve_task = asyncio.create_task(self._server.serve())

        # Wait briefly for uvicorn to actually bind
        for _ in range(20):
            await asyncio.sleep(0.05)
            if self._server.started or self._serve_task.done():
                break

        if not self._server.started:
            self._server.should_exit = True
            if self._serve_task and not self._serve_task.done():
                self._serve_task.cancel()
            self._serve_task = None
            self._server = None
            raise RuntimeError(
                f"Display server failed to start on port {self._port}. "
                f"Check for port conflicts or firewall rules."
            )

        # Register atexit so ctrl+c / crashes still release the port
        atexit.register(self._force_shutdown)
        logger.info("Display server started on http://%s:%d", self._host, self._port)

    @staticmethod
    def _port_is_free(port: int) -> bool:
        """Return True if the given port can be bound.

        Uses SO_REUSEADDR to match uvicorn's default behavior — sockets
        in TIME_WAIT from a recently killed process won't block the check.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", port))
                return True
            except OSError:
                return False

    @staticmethod
    def _free_port(port: int) -> None:
        """Kill any stale process holding the given port."""
        if DisplayServer._port_is_free(port):
            return

        # Port is occupied — find and kill the holder
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-t"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            my_pid = os.getpid()
            for pid_str in result.stdout.strip().splitlines():
                pid = int(pid_str)
                if pid != my_pid:
                    os.kill(pid, signal.SIGTERM)
                    logger.warning("Killed stale process %d on port %d", pid, port)
            # Give the OS a moment to release the socket
            time.sleep(0.3)
        except Exception:
            logger.warning("Could not free port %d", port)

    def _force_shutdown(self) -> None:
        """Atexit handler: forcefully signal uvicorn to stop."""
        if self._server is not None:
            self._server.should_exit = True

    async def push_commentary(
        self,
        text: str,
        team_name: str,
        *,
        emotion: str = "",
        sentence_index: int = 0,
        is_final: bool = False,
    ) -> None:
        """Broadcast commentary text to all connected display clients.

        Feature D: Optional emotion, sentence_index, and is_final fields
        are included in the message for richer audience display rendering.
        """
        msg: dict = {"type": "commentary", "text": text, "team_name": team_name}
        if emotion:
            msg["emotion"] = emotion
        msg["sentence_index"] = sentence_index
        msg["is_final"] = is_final
        await self._manager.broadcast(msg)

    async def push_question(self, text: str, team_name: str) -> None:
        """Broadcast a Q&A question to all connected display clients."""
        await self._manager.broadcast({
            "type": "question",
            "text": text,
            "team_name": team_name,
        })

    async def push_score_intro(self, team_name: str) -> None:
        """Broadcast score intro to signal the start of a score reveal."""
        await self._manager.broadcast({
            "type": "score_intro",
            "team_name": team_name,
        })

    async def push_criterion_reveal(
        self, name: str, score: float, weight: float, justification: str,
    ) -> None:
        """Broadcast a single criterion score for staggered reveal."""
        await self._manager.broadcast({
            "type": "score_criterion",
            "name": name,
            "score": score,
            "weight": weight,
            "justification": justification,
        })

    async def push_total_score(
        self, team_name: str, total_score: float, track: str,
    ) -> None:
        """Broadcast the final weighted total score with dramatic reveal."""
        await self._manager.broadcast({
            "type": "score_total",
            "team_name": team_name,
            "total_score": total_score,
            "track": track,
        })

    async def push_deliberation_ranking(
        self, rank: int, team_name: str, total_score: float, track: str, reasoning: str,
    ) -> None:
        """Broadcast a single team's deliberation ranking to display clients."""
        await self._manager.broadcast({
            "type": "deliberation_ranking",
            "rank": rank,
            "team_name": team_name,
            "total_score": total_score,
            "track": track,
            "reasoning": reasoning,
        })

    async def push_deliberation_narrative(self, narrative: str) -> None:
        """Broadcast the overall deliberation narrative to display clients."""
        await self._manager.broadcast({
            "type": "deliberation_narrative",
            "narrative": narrative,
        })

    async def push_injection_blocked(
        self, category: str, confidence: str, roast: str, team_name: str,
    ) -> None:
        """Broadcast an injection-blocked notification to audience display clients.

        Feature C: Called when an injection attempt is detected so the
        audience display can show a dramatic blocked-injection screen.
        """
        await self._manager.broadcast({
            "type": "injection_blocked",
            "category": category,
            "confidence": confidence,
            "roast": roast,
            "team_name": team_name,
        })

    async def push_capture_started(self, team_name: str, track: str) -> None:
        """Broadcast capture-started notification to audience display clients.

        Feature E: Called when a demo starts capturing so the audience
        display can show a "thinking" / waiting screen.
        """
        await self._manager.broadcast({
            "type": "capture_started",
            "team_name": team_name,
            "track": track,
        })

    async def push_intermission(
        self, leaderboard: list[dict], total_injections: int,
    ) -> None:
        """Broadcast intermission leaderboard to audience display clients.

        Feature F: Called after each demo resets to idle so the audience
        display can show the running leaderboard between teams.
        """
        await self._manager.broadcast({
            "type": "intermission",
            "leaderboard": leaderboard,
            "total_injections": total_injections,
        })

    async def clear(self) -> None:
        """Clear the display on all connected clients."""
        await self._manager.broadcast({"type": "clear"})

    async def stop(self) -> None:
        """Signal uvicorn shutdown and cancel the serve task."""
        if self._server is not None:
            self._server.should_exit = True
        if self._serve_task is not None:
            try:
                await asyncio.wait_for(self._serve_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._serve_task.cancel()
            self._serve_task = None
        logger.info("Display server stopped")
