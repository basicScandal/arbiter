"""Human judge score integration.

Accepts human judge scores and blends them with Arbiter's AI scores.
Blend formula: final = (ai_weight * ai_score) + (human_weight * human_score)
Default: 70% AI + 30% human (configurable).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path

from pydantic import BaseModel, Field

from src.scoring.models import CriterionScore
from src.scoring.store import ScoreStore
from src.utils import sanitize_team_name, resolve_team_slug

logger = logging.getLogger(__name__)

HUMAN_SCORES_DIR = Path("data/human_scores")

# Blend weights (configurable via environment)
AI_WEIGHT = float(os.environ.get("ARBITER_AI_WEIGHT", "0.7"))
HUMAN_WEIGHT = float(os.environ.get("ARBITER_HUMAN_WEIGHT", "0.3"))


class HumanScore(BaseModel):
    """A human judge's score for a team."""

    judge_name: str
    team_name: str
    total_score: float = Field(ge=0, le=10)
    notes: str = ""
    submitted_at: float = 0.0


class BlendedScorecard(BaseModel):
    """A scorecard that combines AI and human scores."""

    team_name: str
    track: str
    ai_score: float
    human_score: float
    blended_score: float
    ai_weight: float
    human_weight: float
    ai_criteria: list[CriterionScore]
    track_bonus: CriterionScore | None = None
    human_judges: list[HumanScore]
    blended_at: float


class HumanScoreStore:
    """Persists and loads human judge scores."""

    def __init__(self, scores_dir: str = str(HUMAN_SCORES_DIR)) -> None:
        self._dir = Path(scores_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    async def save(self, score: HumanScore) -> Path:
        """Save a human score. Multiple judges per team are stored in a list."""
        sanitized = resolve_team_slug(score.team_name)
        path = self._dir / f"{sanitized}.json"

        # Load existing scores for this team
        existing: list[dict] = []
        if path.exists():
            raw = await asyncio.to_thread(path.read_text)
            existing = json.loads(raw)

        existing.append(score.model_dump())
        data = json.dumps(existing, indent=2, default=str)
        await asyncio.to_thread(path.write_text, data)
        return path

    async def load(self, team_name: str) -> list[HumanScore]:
        """Load all human scores for a team."""
        sanitized = sanitize_team_name(team_name)
        path = self._dir / f"{sanitized}.json"
        if not path.exists():
            return []
        raw = await asyncio.to_thread(path.read_text)
        entries = json.loads(raw)
        return [HumanScore(**e) for e in entries]

    async def load_all_teams(self) -> dict[str, list[HumanScore]]:
        """Load human scores grouped by team."""
        result: dict[str, list[HumanScore]] = {}
        for path in self._dir.glob("*.json"):
            raw = await asyncio.to_thread(path.read_text)
            entries = json.loads(raw)
            scores = [HumanScore(**e) for e in entries]
            if scores:
                result[scores[0].team_name] = scores
        return result


async def blend_scores(team_name: str) -> BlendedScorecard | None:
    """Blend AI and human scores for a team.

    Human score = average of all human judge scores for this team.
    Blended = (AI_WEIGHT * ai_score) + (HUMAN_WEIGHT * avg_human_score)

    Returns None if no AI scorecard exists.
    """
    score_store = ScoreStore(scores_dir="data/scores")
    human_store = HumanScoreStore()

    ai_card = await score_store.load(team_name)
    if ai_card is None:
        return None

    human_scores = await human_store.load(team_name)

    if not human_scores:
        # No human scores — blended = AI only
        return BlendedScorecard(
            team_name=ai_card.team_name,
            track=ai_card.track,
            ai_score=ai_card.total_score,
            human_score=0.0,
            blended_score=ai_card.total_score,
            ai_weight=1.0,
            human_weight=0.0,
            ai_criteria=ai_card.criteria,
            track_bonus=ai_card.track_bonus,
            human_judges=[],
            blended_at=time.time(),
        )

    avg_human = sum(s.total_score for s in human_scores) / len(human_scores)
    blended = (AI_WEIGHT * ai_card.total_score) + (HUMAN_WEIGHT * avg_human)

    return BlendedScorecard(
        team_name=ai_card.team_name,
        track=ai_card.track,
        ai_score=ai_card.total_score,
        human_score=avg_human,
        blended_score=round(blended, 2),
        ai_weight=AI_WEIGHT,
        human_weight=HUMAN_WEIGHT,
        ai_criteria=ai_card.criteria,
        track_bonus=ai_card.track_bonus,
        human_judges=human_scores,
        blended_at=time.time(),
    )
