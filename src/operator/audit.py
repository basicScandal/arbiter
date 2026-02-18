"""Append-only audit log for operator commands.

Writes one JSON line per operator action to data/audit.jsonl, capturing
command details, team context, state transitions, and timing for post-event
accountability and timeline reconstruction.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_AUDIT_PATH = Path("data/audit.jsonl")


def log_command(
    action: str,
    *,
    success: bool,
    team_name: str = "",
    track: str = "",
    state_before: str = "",
    state_after: str = "",
    detail: str = "",
) -> None:
    """Append a single audit entry to the JSONL log.

    Args:
        action: The operator command (start, stop, qa, etc.).
        success: Whether the command succeeded.
        team_name: Team name if applicable.
        track: Challenge track if applicable.
        state_before: Demo machine state before the command.
        state_after: Demo machine state after the command.
        detail: Optional extra context (error messages, etc.).
    """
    entry = {
        "timestamp": time.time(),
        "action": action,
        "success": success,
        "team_name": team_name,
        "track": track,
        "state_before": state_before,
        "state_after": state_after,
    }
    if detail:
        entry["detail"] = detail

    try:
        _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _AUDIT_PATH.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        logger.warning("Failed to write audit log entry", exc_info=True)
