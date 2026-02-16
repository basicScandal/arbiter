"""Persists per-demo structured observations as JSON files for deliberation.

Stores one JSON file per team in a configurable directory. Files are
human-readable and named by team (sanitized for filesystem safety).
Follows the identical pattern to ScoreStore from Phase 4.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

from src.memory.models import DemoMemory

logger = logging.getLogger(__name__)


class MemoryStore:
    """Persists per-demo observations as JSON files for deliberation.

    Stores one JSON file per team in a configurable directory.
    Files are human-readable and named by team (sanitized for filesystem).
    """

    def __init__(self, observations_dir: str = "data/observations") -> None:
        self._dir = Path(observations_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sanitize_team_name(team_name: str) -> str:
        """Sanitize a team name for filesystem use.

        Replaces spaces with underscores, strips non-alphanumeric characters
        except underscores and hyphens, and lowercases the result.
        """
        name = team_name.replace(" ", "_")
        name = re.sub(r"[^a-zA-Z0-9_\-]", "", name)
        return name.lower()

    async def save(self, memory: DemoMemory) -> Path:
        """Save a demo memory as a pretty-printed JSON file.

        Args:
            memory: The structured demo observations to persist.

        Returns:
            The Path of the saved JSON file.
        """
        sanitized = self._sanitize_team_name(memory.team_name)
        path = self._dir / f"{sanitized}.json"
        data = json.dumps(memory.model_dump(), indent=2, default=str)
        await asyncio.to_thread(path.write_text, data)
        logger.info("Demo memory saved to %s", path)
        return path

    async def load(self, team_name: str) -> DemoMemory | None:
        """Load a demo memory for a specific team.

        Args:
            team_name: The team name (will be sanitized for lookup).

        Returns:
            The DemoMemory if found, None otherwise.
        """
        sanitized = self._sanitize_team_name(team_name)
        path = self._dir / f"{sanitized}.json"
        if not path.exists():
            return None
        raw = await asyncio.to_thread(path.read_text)
        return DemoMemory.model_validate_json(raw)

    async def load_all(self) -> list[DemoMemory]:
        """Load all saved demo memories from the observations directory.

        Returns:
            List of all persisted DemoMemory instances (for deliberation).
        """
        memories: list[DemoMemory] = []
        for path in sorted(self._dir.glob("*.json")):
            try:
                raw = await asyncio.to_thread(path.read_text)
                memories.append(DemoMemory.model_validate_json(raw))
            except Exception:
                logger.warning("Failed to parse demo memory from %s", path)
        return memories
