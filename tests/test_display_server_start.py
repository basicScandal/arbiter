"""Tests for DisplayServer.start() error handling.

Validates that port conflicts and startup failures raise RuntimeError
instead of silently returning, so callers can degrade gracefully.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.commentary.display_server import DisplayServer


class TestStartPortConflict:
    """Tests for port-in-use detection at startup."""

    @pytest.mark.asyncio
    async def test_raises_on_port_in_use(self):
        """start() raises RuntimeError when port is still occupied after cleanup."""
        server = DisplayServer(host="127.0.0.1", port=9999)

        with patch.object(DisplayServer, "_free_port"):
            with patch.object(DisplayServer, "_port_is_free", return_value=False):
                with pytest.raises(RuntimeError, match="port 9999 is already in use"):
                    await server.start()

    @pytest.mark.asyncio
    async def test_error_includes_port_number(self):
        """Error message includes the conflicting port for diagnostics."""
        server = DisplayServer(host="127.0.0.1", port=4321)

        with patch.object(DisplayServer, "_free_port"):
            with patch.object(DisplayServer, "_port_is_free", return_value=False):
                with pytest.raises(RuntimeError, match="4321"):
                    await server.start()

    @pytest.mark.asyncio
    async def test_error_includes_lsof_hint(self):
        """Error message includes lsof command hint for troubleshooting."""
        server = DisplayServer(host="127.0.0.1", port=9999)

        with patch.object(DisplayServer, "_free_port"):
            with patch.object(DisplayServer, "_port_is_free", return_value=False):
                with pytest.raises(RuntimeError, match="lsof"):
                    await server.start()


class TestStartUvicornFailure:
    """Tests for uvicorn failing to bind after port check passes."""

    @pytest.mark.asyncio
    async def test_raises_when_uvicorn_fails_to_start(self):
        """start() raises RuntimeError when uvicorn doesn't bind in time."""
        server = DisplayServer(host="127.0.0.1", port=9999)

        with (
            patch.object(DisplayServer, "_free_port"),
            patch.object(DisplayServer, "_port_is_free", return_value=True),
            patch("src.commentary.display_server.uvicorn.Server") as MockServer,
            patch("src.commentary.display_server.uvicorn.Config"),
        ):
            mock_server = MockServer.return_value
            mock_server.started = False
            mock_server.should_exit = False

            async def fake_serve():
                pass  # never sets started=True

            mock_server.serve = fake_serve

            with pytest.raises(RuntimeError, match="failed to start"):
                await server.start()
