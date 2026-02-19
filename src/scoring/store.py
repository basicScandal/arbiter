"""Persists demo scorecards as JSON files for Phase 5 deliberation.

Stores one JSON file per team in a configurable directory. Files are
human-readable and named by team (sanitized for filesystem safety).
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from src.scoring.models import DemoScorecard
from src.utils import sanitize_team_name

logger = logging.getLogger(__name__)


class ScoreStore:
    """Persists demo scorecards as JSON files for Phase 5 deliberation.

    Stores one JSON file per team in a configurable directory.
    Files are human-readable and named by team (sanitized for filesystem).
    """

    def __init__(self, scores_dir: str = "data/scores") -> None:
        self._scores_dir = Path(scores_dir)
        self._scores_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, scorecard: DemoScorecard) -> Path:
        """Save a scorecard as a pretty-printed JSON file.

        Args:
            scorecard: The completed demo scorecard to persist.

        Returns:
            The Path of the saved JSON file.
        """
        sanitized = sanitize_team_name(scorecard.team_name)
        path = self._scores_dir / f"{sanitized}.json"
        data = json.dumps(scorecard.model_dump(), indent=2, default=str)
        await asyncio.to_thread(path.write_text, data)
        logger.info("Scorecard saved to %s", path)
        return path

    async def load(self, team_name: str) -> DemoScorecard | None:
        """Load a scorecard for a specific team.

        Args:
            team_name: The team name (will be sanitized for lookup).

        Returns:
            The DemoScorecard if found, None otherwise.
        """
        sanitized = sanitize_team_name(team_name)
        path = self._scores_dir / f"{sanitized}.json"
        if not path.exists():
            return None
        raw = await asyncio.to_thread(path.read_text)
        return DemoScorecard.model_validate_json(raw)

    async def load_all(self) -> list[DemoScorecard]:
        """Load all saved scorecards from the scores directory.

        Returns:
            List of all persisted DemoScorecards (for Phase 5 deliberation).
        """
        scorecards: list[DemoScorecard] = []
        for path in sorted(self._scores_dir.glob("*.json")):
            try:
                raw = await asyncio.to_thread(path.read_text)
                scorecards.append(DemoScorecard.model_validate_json(raw))
            except Exception:
                logger.warning("Failed to parse scorecard from %s", path)
        return scorecards
