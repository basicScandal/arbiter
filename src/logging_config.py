"""Centralized logging configuration for Arbiter.

Configures the root logger with optional file and console handlers.
Controlled via environment variables so main, rehearsal, and replay
all use a single consistent setup.
"""

from __future__ import annotations

import json
import logging
import os
import sys


def _json_formatter(record: logging.LogRecord) -> str:
    """Format a log record as a single-line JSON object."""
    payload = {
        "ts": record.created,
        "level": record.levelname,
        "logger": record.name,
        "msg": record.getMessage(),
    }
    if record.exc_info:
        payload["exc"] = record.exc_text or str(record.exc_info[1])
    return json.dumps(payload) + "\n"


class JsonFormatter(logging.Formatter):
    """Formatter that emits one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        return _json_formatter(record)


def configure_logging(
    *,
    console: bool | None = None,
    log_file: str | None = None,
    level: str | None = None,
    json_format: bool | None = None,
    rehearsal: bool = False,
) -> None:
    """Configure the root logger for the process.

    Args:
        console: If True, add a StreamHandler to stderr. If None, use
            ARBITER_LOG_CONSOLE env (true/1/yes → True).
        log_file: Path for file handler. If None, use ARBITER_LOG_FILE
            (default /tmp/arbiter.log). Empty string disables file logging.
        level: Log level name (DEBUG, INFO, WARNING, ERROR). If None,
            use ARBITER_LOG_LEVEL (default DEBUG).
        json_format: If True, use JSON lines format. If None, use
            ARBITER_LOG_JSON env (true/1/yes → True).
        rehearsal: If True, use a friendlier console format and default
            console=True for rehearsal mode.
    """
    level_name = (level or os.getenv("ARBITER_LOG_LEVEL", "DEBUG")).upper()
    log_level = getattr(logging, level_name, logging.DEBUG)

    use_json = json_format if json_format is not None else (
        os.getenv("ARBITER_LOG_JSON", "").lower() in ("true", "1", "yes")
    )
    use_console = console if console is not None else (
        os.getenv("ARBITER_LOG_CONSOLE", "false").lower() in ("true", "1", "yes")
    )
    if rehearsal:
        use_console = True

    file_path = log_file if log_file is not None else os.getenv("ARBITER_LOG_FILE", "/tmp/arbiter.log")

    if use_json:
        formatter: logging.Formatter = JsonFormatter()
        console_formatter = JsonFormatter()
    else:
        date_fmt = "%H:%M:%S" if not rehearsal else "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt=date_fmt,
        )
        console_formatter = (
            logging.Formatter("%(levelname)-8s %(message)s")
            if rehearsal
            else logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt=date_fmt,
            )
        )

    root = logging.getLogger()
    root.setLevel(log_level)

    # Remove any handlers we might have added in a prior call (e.g. tests)
    for h in root.handlers[:]:
        if getattr(h, "_arbiter_configured", False):
            root.removeHandler(h)

    if file_path:
        try:
            file_handler = logging.FileHandler(file_path, mode="a")
        except OSError:
            file_handler = logging.StreamHandler(sys.stderr)
            file_handler.setLevel(logging.WARNING)
            file_handler.setFormatter(console_formatter)
            file_handler.stream.write(f"[arbiter] Could not open log file {file_path!r}, logging to stderr\n")
        else:
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
        file_handler._arbiter_configured = True  # type: ignore[attr-defined]
        root.addHandler(file_handler)

    if use_console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(console_formatter)
        console_handler._arbiter_configured = True  # type: ignore[attr-defined]
        root.addHandler(console_handler)
