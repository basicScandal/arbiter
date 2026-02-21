"""Tests for the OBS Stream Overlay at /stream.

Verifies that the stream.html template exists with the required structure
and that the /stream route is correctly registered on the FastAPI app.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.commentary.display_server import DisplayServer

# Path to the template file under test
_TEMPLATE_PATH = Path(__file__).parent.parent / "src/commentary/templates/stream.html"


# ---------------------------------------------------------------------------
# 1. Template file existence
# ---------------------------------------------------------------------------


def test_stream_html_exists():
    """stream.html template file exists in the templates directory."""
    assert _TEMPLATE_PATH.exists(), f"stream.html not found at {_TEMPLATE_PATH}"


def test_stream_html_is_not_empty():
    """stream.html template is not empty."""
    assert _TEMPLATE_PATH.stat().st_size > 0


# ---------------------------------------------------------------------------
# 2. Key structural elements
# ---------------------------------------------------------------------------


def _html() -> str:
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def test_html_has_transparent_background():
    """body has transparent background for OBS chromakey."""
    assert "background: transparent" in _html()


def test_html_has_lower_third_element():
    """lower-third container element is present."""
    assert "lower-third" in _html()


def test_html_has_injection_bar_element():
    """injection-bar element is present for blocked-injection alerts."""
    assert "injection-bar" in _html()


def test_html_references_ws_display_endpoint():
    """WebSocket connection targets /ws/display."""
    assert "ws/display" in _html()


def test_html_fixed_dimensions_for_broadcast():
    """HTML specifies 1920x1080 fixed dimensions for broadcast compositing."""
    html = _html()
    assert "1920px" in html
    assert "1080px" in html


# ---------------------------------------------------------------------------
# 3. Message type handlers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("msg_type", [
    "clear",
    "commentary",
    "question",
    "score_intro",
    "score_criterion",
    "score_total",
    "deliberation_ranking",
    "deliberation_narrative",
    "capture_started",
    "injection_blocked",
    "intermission",
])
def test_html_handles_message_type(msg_type: str):
    """Switch-case handler exists for each expected WebSocket message type."""
    assert f"case '{msg_type}':" in _html(), (
        f"No handler found for message type '{msg_type}' in stream.html"
    )


# ---------------------------------------------------------------------------
# 4. Heartbeat support
# ---------------------------------------------------------------------------


def test_html_responds_to_ping():
    """Client sends pong in response to server ping messages."""
    html = _html()
    assert "ping" in html
    assert "pong" in html


def test_html_sends_pong_on_ping():
    """Pong response is sent via ws.send when ping is received."""
    html = _html()
    # The pong response block should explicitly check for ping type and send pong
    assert "type: 'pong'" in html or '"pong"' in html


# ---------------------------------------------------------------------------
# 5. XSS prevention
# ---------------------------------------------------------------------------


def test_html_has_esc_function():
    """esc() helper function is defined for HTML escaping."""
    assert "function esc(" in _html()


def test_esc_uses_textcontent():
    """esc() uses textContent assignment to safely escape user content."""
    assert "textContent" in _html()


def test_esc_returns_innerhtml():
    """esc() retrieves innerHTML after textContent assignment (safe escape pattern)."""
    assert "d.innerHTML" in _html()


# ---------------------------------------------------------------------------
# 6. Auto-reconnect
# ---------------------------------------------------------------------------


def test_html_auto_reconnects_on_close():
    """WebSocket reconnects automatically after close (resilient to drops)."""
    html = _html()
    assert "onclose" in html
    assert "connect" in html


# ---------------------------------------------------------------------------
# 7. /stream route registration
# ---------------------------------------------------------------------------


def test_stream_route_is_registered():
    """/stream GET route is registered on the DisplayServer FastAPI app."""
    server = DisplayServer(host="127.0.0.1", port=9998)
    routes = {getattr(r, "path", None) for r in server.app.routes}
    assert "/stream" in routes, f"/stream not in routes: {routes}"


def test_stream_route_returns_200():
    """/stream endpoint returns HTTP 200 with HTML content."""
    server = DisplayServer(host="127.0.0.1", port=9997)
    client = TestClient(server.app)
    response = client.get("/stream")
    assert response.status_code == 200


def test_stream_route_returns_html_content_type():
    """/stream endpoint returns text/html content type."""
    server = DisplayServer(host="127.0.0.1", port=9996)
    client = TestClient(server.app)
    response = client.get("/stream")
    assert "text/html" in response.headers.get("content-type", "")


def test_stream_response_contains_lower_third():
    """/stream response body contains the lower-third element."""
    server = DisplayServer(host="127.0.0.1", port=9995)
    client = TestClient(server.app)
    response = client.get("/stream")
    assert "lower-third" in response.text


def test_stream_response_contains_ws_display():
    """/stream response body references the ws/display WebSocket endpoint."""
    server = DisplayServer(host="127.0.0.1", port=9994)
    client = TestClient(server.app)
    response = client.get("/stream")
    assert "ws/display" in response.text
