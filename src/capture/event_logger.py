"""Append-only event log capturing every event bus event to JSONL.

Subscribes to all events via subscribe_all() and writes one JSON line per
event to data/events.jsonl. Binary fields (frame data, audio) are excluded
to keep the log readable and compact. All other event data — timestamps,
team names, scores, commentary, roasts, injection attempts — is preserved
for full post-event replay and analysis.

Thread-safe via asyncio.to_thread for file I/O.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from src.capture.models import CaptureEvent

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path("data/events.jsonl")

# Fields containing binary data that should not be serialized
_BINARY_FIELDS = {"raw_frame", "jpeg_data", "data"}

# High-frequency events that are logged with minimal payload to avoid
# bloating the event log (frame_captured fires ~30x/sec)
_MINIMAL_EVENTS = {"frame_captured", "tts_speaking", "tts_finished"}


def _strip_binary(obj: object) -> object:
    """Recursively strip binary fields from a dict/list structure."""
    if isinstance(obj, dict):
        return {
            k: _strip_binary(v)
            for k, v in obj.items()
            if k not in _BINARY_FIELDS
        }
    if isinstance(obj, list):
        return [_strip_binary(item) for item in obj]
    if isinstance(obj, bytes):
        return f"<{len(obj)} bytes>"
    return obj


class EventLogger:
    """Logs all event bus events to an append-only JSONL file.

    Usage:
        logger = EventLogger()
        event_bus.subscribe_all(logger.on_event)
    """

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._path, "a")  # noqa: SIM115
        logger.info("Event logger writing to %s", self._path)

    async def on_event(self, event: CaptureEvent) -> None:
        """Serialize and append an event to the JSONL log."""
        try:
            entry = self._serialize(event)
            line = json.dumps(entry, default=str) + "\n"
            await asyncio.to_thread(self._write_line, line)
        except Exception:
            logger.debug(
                "Failed to log event %s", event.event_type, exc_info=True,
            )

    def _write_line(self, line: str) -> None:
        """Write and flush a line to the log file (runs in thread pool)."""
        self._file.write(line)
        self._file.flush()

    def _serialize(self, event: CaptureEvent) -> dict:
        """Convert an event to a JSON-serializable dict."""
        if event.event_type in _MINIMAL_EVENTS:
            return {
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "logged_at": time.time(),
            }

        # Full serialization with binary stripping
        try:
            data = event.model_dump()
        except Exception:
            data = {"event_type": event.event_type}

        cleaned = _strip_binary(data)
        if isinstance(cleaned, dict):
            cleaned["logged_at"] = time.time()
        return cleaned

    def close(self) -> None:
        """Flush and close the log file."""
        try:
            self._file.flush()
            self._file.close()
        except Exception:
            pass

    @staticmethod
    def load(path: Path = _DEFAULT_PATH) -> list[dict]:
        """Load all events from the JSONL log file.

        Returns a list of event dicts. Skips malformed lines.
        """
        if not path.exists():
            return []

        events: list[dict] = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return events
