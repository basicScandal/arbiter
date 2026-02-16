"""FastAPI display server with WebSocket broadcast for audience text display.

Runs an async web server that pushes commentary and Q&A text to connected
browser clients via WebSocket. Designed for projection on a large screen
at NEBULA:FOG 2026.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


class ConnectionManager:
    """Manage active WebSocket connections and broadcast messages."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await ws.accept()
        self.active.append(ws)
        logger.info("Display client connected (%d active)", len(self.active))

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        if ws in self.active:
            self.active.remove(ws)
        logger.info("Display client disconnected (%d active)", len(self.active))

    async def broadcast(self, message: dict) -> None:
        """Send a JSON message to all connected clients.

        Silently removes clients that have disconnected.
        """
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

    def _register_routes(self) -> None:
        """Register HTTP and WebSocket routes on the FastAPI app."""

        @self._app.get("/", response_class=HTMLResponse)
        async def display_page(request: Request) -> HTMLResponse:
            return self._templates.TemplateResponse("display.html", {"request": request})

        @self._app.websocket("/ws/display")
        async def websocket_endpoint(ws: WebSocket) -> None:
            await self._manager.connect(ws)
            try:
                while True:
                    # Keep connection alive; client doesn't send meaningful data
                    await ws.receive_text()
            except WebSocketDisconnect:
                self._manager.disconnect(ws)

    async def start(self) -> None:
        """Start uvicorn as a non-blocking asyncio task."""
        config = uvicorn.Config(
            app=self._app,
            host=self._host,
            port=self._port,
            log_level="warning",
        )
        self._server = uvicorn.Server(config)
        self._serve_task = asyncio.create_task(self._server.serve())
        logger.info("Display server started on http://%s:%d", self._host, self._port)

    async def push_commentary(self, text: str, team_name: str) -> None:
        """Broadcast commentary text to all connected display clients."""
        await self._manager.broadcast({
            "type": "commentary",
            "text": text,
            "team_name": team_name,
        })

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
