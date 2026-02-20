"""Canonical track list loaded from shared/tracks.json."""
from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "../../shared/tracks.json"


def _load() -> dict:
    return json.loads(_CONFIG_PATH.read_text())


_config = _load()

TRACKS: list[str] = _config["tracks"]
VALID_TRACKS: set[str] = set(TRACKS)
DEFAULT_TRACK: str = _config["default_track"]
