"""Post-event data export — comprehensive event data as JSON."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

SCORES_DIR = Path("data/scores")
OBSERVATIONS_DIR = Path("data/observations")
COMMENTARY_DIR = Path("data/commentary")
HUMAN_SCORES_DIR = Path("data/human_scores")
AUDIT_LOG = Path("data/audit.jsonl")
EVENTS_LOG = Path("data/events.jsonl")
DELIBERATION_DIR = Path("data/deliberation")


class TeamExport(BaseModel):
    """Complete data export for a single team."""
    team_name: str
    track: str
    ai_score: float
    scorecard: dict | None = None
    commentary: dict | None = None
    observations: dict | None = None
    human_scores: list[dict] = []


class EventExport(BaseModel):
    """Complete event data export."""
    event_name: str
    exported_at: float
    team_count: int
    teams: list[TeamExport]
    deliberation: dict | None = None
    audit_log: list[dict] = []
    event_log: list[dict] = []


async def export_event_data(
    *,
    include_audit: bool = False,
    include_observations: bool = True,
    include_events: bool = False,
) -> EventExport:
    """Assemble comprehensive event data export.

    Args:
        include_audit: Whether to include the operator command audit log.
        include_observations: Whether to include raw observations per team.
    """
    from src.scoring.store import ScoreStore

    score_store = ScoreStore(scores_dir=str(SCORES_DIR))
    scorecards = await score_store.load_all()

    teams: list[TeamExport] = []
    for sc in sorted(scorecards, key=lambda s: s.total_score, reverse=True):
        team = TeamExport(
            team_name=sc.team_name,
            track=sc.track,
            ai_score=sc.total_score,
            scorecard=sc.model_dump(),
        )

        # Load commentary
        from src.utils import sanitize_team_name
        sanitized = sanitize_team_name(sc.team_name)

        commentary_path = COMMENTARY_DIR / f"{sanitized}.json"
        if commentary_path.exists():
            try:
                raw = await asyncio.to_thread(commentary_path.read_text)
                team.commentary = json.loads(raw)
            except Exception:
                logger.debug("Failed to load commentary for %s", sc.team_name)

        # Load observations
        if include_observations:
            obs_path = OBSERVATIONS_DIR / f"{sanitized}.json"
            if obs_path.exists():
                try:
                    raw = await asyncio.to_thread(obs_path.read_text)
                    team.observations = json.loads(raw)
                except Exception:
                    logger.debug("Failed to load observations for %s", sc.team_name)

        # Load human scores
        human_path = HUMAN_SCORES_DIR / f"{sanitized}.json"
        if human_path.exists():
            try:
                raw = await asyncio.to_thread(human_path.read_text)
                team.human_scores = json.loads(raw)
            except Exception:
                logger.debug("Failed to load human scores for %s", sc.team_name)

        teams.append(team)

    # Load deliberation result
    deliberation = None
    delib_path = DELIBERATION_DIR / "result.json"
    if delib_path.exists():
        try:
            raw = await asyncio.to_thread(delib_path.read_text)
            deliberation = json.loads(raw)
        except Exception:
            logger.debug("Failed to load deliberation result")

    # Load audit log
    audit_entries: list[dict] = []
    if include_audit and AUDIT_LOG.exists():
        try:
            raw = await asyncio.to_thread(AUDIT_LOG.read_text)
            for line in raw.strip().splitlines():
                if line.strip():
                    audit_entries.append(json.loads(line))
        except Exception:
            logger.debug("Failed to load audit log")

    # Load event log
    event_entries: list[dict] = []
    if include_events and EVENTS_LOG.exists():
        try:
            from src.capture.event_logger import EventLogger
            event_entries = await asyncio.to_thread(EventLogger.load, EVENTS_LOG)
        except Exception:
            logger.debug("Failed to load event log")

    return EventExport(
        event_name="NEBULA:FOG 2026",
        exported_at=time.time(),
        team_count=len(teams),
        teams=teams,
        deliberation=deliberation,
        audit_log=audit_entries,
        event_log=event_entries,
    )


async def export_team_data(team_name: str) -> TeamExport | None:
    """Export all data for a single team."""
    from src.scoring.store import ScoreStore
    from src.utils import sanitize_team_name

    score_store = ScoreStore(scores_dir=str(SCORES_DIR))
    scorecard = await score_store.load(team_name)
    if scorecard is None:
        return None

    sanitized = sanitize_team_name(team_name)
    team = TeamExport(
        team_name=scorecard.team_name,
        track=scorecard.track,
        ai_score=scorecard.total_score,
        scorecard=scorecard.model_dump(),
    )

    # Commentary
    commentary_path = COMMENTARY_DIR / f"{sanitized}.json"
    if commentary_path.exists():
        try:
            raw = await asyncio.to_thread(commentary_path.read_text)
            team.commentary = json.loads(raw)
        except Exception:
            logger.debug("Failed to load commentary for %s", team_name, exc_info=True)

    # Observations
    obs_path = OBSERVATIONS_DIR / f"{sanitized}.json"
    if obs_path.exists():
        try:
            raw = await asyncio.to_thread(obs_path.read_text)
            team.observations = json.loads(raw)
        except Exception:
            logger.debug("Failed to load observations for %s", team_name, exc_info=True)

    # Human scores
    human_path = HUMAN_SCORES_DIR / f"{sanitized}.json"
    if human_path.exists():
        try:
            raw = await asyncio.to_thread(human_path.read_text)
            team.human_scores = json.loads(raw)
        except Exception:
            logger.debug("Failed to load human scores for %s", team_name, exc_info=True)

    return team
