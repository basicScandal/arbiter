"""Generate human-readable and machine-readable replay reports."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.memory.models import DeliberationResult
from src.replay.config import BASE_DIR, DELIBERATION_DIR, SCORES_DIR
from src.scoring.models import DemoScorecard

logger = logging.getLogger(__name__)


async def generate_report() -> None:
    """Generate report.md and report.json from completed replay data."""
    scorecards = await _load_scorecards()
    deliberation = await _load_deliberation()

    md = _build_markdown(scorecards, deliberation)
    js = _build_json(scorecards, deliberation)

    md_path = BASE_DIR / "report.md"
    json_path = BASE_DIR / "report.json"

    await asyncio.to_thread(md_path.write_text, md)
    await asyncio.to_thread(json_path.write_text, json.dumps(js, indent=2, default=str))

    logger.info("Reports written: %s, %s", md_path, json_path)


async def _load_scorecards() -> list[DemoScorecard]:
    """Load all scorecards from replay scores directory."""
    cards: list[DemoScorecard] = []
    scores_dir = Path(SCORES_DIR)
    if not scores_dir.exists():
        return cards
    for path in sorted(scores_dir.glob("*.json")):
        try:
            raw = await asyncio.to_thread(path.read_text)
            cards.append(DemoScorecard.model_validate_json(raw))
        except Exception:
            logger.warning("Failed to parse scorecard: %s", path)
    return cards


async def _load_deliberation() -> DeliberationResult | None:
    """Load deliberation result if available."""
    result_path = Path(DELIBERATION_DIR) / "result.json"
    if not result_path.exists():
        return None
    try:
        raw = await asyncio.to_thread(result_path.read_text)
        return DeliberationResult.model_validate_json(raw)
    except Exception:
        logger.warning("Failed to parse deliberation result")
        return None


def _build_markdown(
    scorecards: list[DemoScorecard],
    deliberation: DeliberationResult | None,
) -> str:
    """Build human-readable markdown report."""
    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append("# NEBULA:FOG:PRIME Replay Report")
    lines.append(f"\nGenerated: {now}")
    lines.append(f"\nTotal demos scored: {len(scorecards)}")

    # Scoreboard (sorted by total_score descending)
    if scorecards:
        sorted_cards = sorted(scorecards, key=lambda c: -c.total_score)
        lines.append("\n## Scoreboard\n")
        lines.append("| Rank | Team | Track | Score |")
        lines.append("|------|------|-------|-------|")
        for i, card in enumerate(sorted_cards, 1):
            lines.append(f"| {i} | {card.team_name} | {card.track} | {card.total_score:.1f} |")

    # Per-team details
    if scorecards:
        lines.append("\n## Score Details\n")
        sorted_cards = sorted(scorecards, key=lambda c: -c.total_score)
        for card in sorted_cards:
            lines.append(f"### {card.team_name} ({card.track})")
            lines.append(f"\n**Total: {card.total_score:.1f}**\n")
            for criterion in card.criteria:
                lines.append(f"- **{criterion.name}** ({criterion.weight:.0%}): {criterion.score:.1f}")
                lines.append(f"  - {criterion.justification}")
            if card.track_bonus:
                lines.append(f"- **{card.track_bonus.name}** (bonus {card.track_bonus.weight:.0%}): {card.track_bonus.score:.1f}")
                lines.append(f"  - {card.track_bonus.justification}")
            lines.append("")

    # Deliberation
    if deliberation:
        lines.append("\n## Deliberation\n")
        lines.append(deliberation.overall_narrative)

        if deliberation.notable_themes:
            lines.append("\n### Notable Themes\n")
            for theme in deliberation.notable_themes:
                lines.append(f"- {theme}")

        if deliberation.rankings:
            lines.append("\n### Rankings with Reasoning\n")
            for ranking in deliberation.rankings:
                lines.append(f"**#{ranking.rank} {ranking.team_name}** ({ranking.track}) — {ranking.total_score:.1f}")
                lines.append(f"\n{ranking.reasoning}\n")
                if ranking.strengths:
                    lines.append("Strengths:")
                    for s in ranking.strengths:
                        lines.append(f"- {s}")
                if ranking.weaknesses:
                    lines.append("Weaknesses:")
                    for w in ranking.weaknesses:
                        lines.append(f"- {w}")
                if ranking.cross_references:
                    lines.append("Cross-references:")
                    for cr in ranking.cross_references:
                        lines.append(f"- {cr}")
                lines.append("")

    return "\n".join(lines)


def _build_json(
    scorecards: list[DemoScorecard],
    deliberation: DeliberationResult | None,
) -> dict:
    """Build machine-readable JSON report."""
    now = datetime.now(timezone.utc).isoformat()
    sorted_cards = sorted(scorecards, key=lambda c: -c.total_score)

    return {
        "generated_at": now,
        "total_demos": len(scorecards),
        "scorecards": [card.model_dump() for card in sorted_cards],
        "deliberation": deliberation.model_dump() if deliberation else None,
    }
