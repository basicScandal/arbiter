"""Loader for real NEBULA:FOG demo observation data.

Reads DemoMemory JSON files from data/replay/observations/ and converts
them to SanitizedOutput for use in scoring and pipeline tests. Loaded at
module scope so pytest.mark.parametrize can generate per-team test IDs
at collection time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

from src.defense.models import SanitizedOutput

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "replay" / "observations"


class DemoMemory(NamedTuple):
    """Mirror of the JSON schema in data/replay/observations/*.json."""

    team_name: str
    track: str
    observations: list[str]
    transcripts: list[str]
    injection_attempts: int
    demo_duration: float
    stored_at: float


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_all() -> list[DemoMemory]:
    """Load all DemoMemory JSON files, sorted by team name."""
    memories: list[DemoMemory] = []
    for path in sorted(_DATA_DIR.glob("*.json")):
        with open(path) as f:
            data = json.load(f)
        memories.append(
            DemoMemory(
                team_name=data["team_name"],
                track=data["track"],
                observations=data["observations"],
                transcripts=data["transcripts"],
                injection_attempts=data["injection_attempts"],
                demo_duration=data["demo_duration"],
                stored_at=data["stored_at"],
            )
        )
    memories.sort(key=lambda m: m.team_name)
    return memories


def to_sanitized(memory: DemoMemory) -> SanitizedOutput:
    """Convert a DemoMemory to SanitizedOutput for scoring.

    injection_attempts is an int count in DemoMemory but a list in
    SanitizedOutput, so we convert count -> empty list (the actual
    InjectionAttempt objects aren't stored in the replay data).
    """
    return SanitizedOutput(
        team_name=memory.team_name,
        observations=list(memory.observations),
        transcripts=list(memory.transcripts),
        injection_attempts=[],
        demo_duration=memory.demo_duration,
    )


# ---------------------------------------------------------------------------
# Module-level constant (loaded once at import time)
# ---------------------------------------------------------------------------

ALL_DEMOS: list[DemoMemory] = load_all()
