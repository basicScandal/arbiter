"""Per-team report card HTML generation."""
from __future__ import annotations

import html
import json
import logging
from pathlib import Path

from src.scoring.models import DemoScorecard

logger = logging.getLogger(__name__)

SCORES_DIR = Path("data/scores")
COMMENTARY_DIR = Path("data/commentary")


async def generate_report_card_html(team_name: str) -> str | None:
    """Generate a styled HTML report card for a team.

    Returns HTML string or None if team data not found.
    """
    # Load scorecard
    from src.scoring.store import ScoreStore
    score_store = ScoreStore(scores_dir=str(SCORES_DIR))
    scorecard = await score_store.load(team_name)
    if scorecard is None:
        return None

    # Load commentary (optional — card still works without it)
    commentary_text = ""
    try:
        from src.utils import sanitize_team_name
        name = sanitize_team_name(team_name)
        commentary_path = COMMENTARY_DIR / f"{name}.json"
        if commentary_path.exists():
            import asyncio
            raw = await asyncio.to_thread(commentary_path.read_text)
            data = json.loads(raw)
            commentary_text = data.get("text", "")
    except Exception:
        logger.debug("Could not load commentary for %s", team_name)

    return _render_html(scorecard, commentary_text)


def _render_html(scorecard: DemoScorecard, commentary: str) -> str:
    """Render the report card as styled HTML."""
    # Build criteria rows
    criteria_rows = ""
    for c in scorecard.criteria:
        bar_width = c.score * 10  # 0-100%
        criteria_rows += f"""
        <tr>
            <td class="criterion-name">{html.escape(c.name)}</td>
            <td class="criterion-weight">×{c.weight}</td>
            <td class="criterion-score">
                <div class="score-bar-bg">
                    <div class="score-bar" style="width: {bar_width}%"></div>
                </div>
                <span class="score-value">{c.score:.1f}</span>
            </td>
        </tr>
        <tr class="justification-row">
            <td colspan="3" class="justification">{html.escape(c.justification)}</td>
        </tr>"""

    # Track bonus row
    bonus_html = ""
    if scorecard.track_bonus:
        tb = scorecard.track_bonus
        bar_width = tb.score * 10
        bonus_html = f"""
        <tr class="bonus-row">
            <td class="criterion-name bonus">{html.escape(tb.name)}</td>
            <td class="criterion-weight">×{tb.weight}</td>
            <td class="criterion-score">
                <div class="score-bar-bg">
                    <div class="score-bar bonus-bar" style="width: {bar_width}%"></div>
                </div>
                <span class="score-value bonus">{tb.score:.1f}</span>
            </td>
        </tr>
        <tr class="justification-row">
            <td colspan="3" class="justification">{html.escape(tb.justification)}</td>
        </tr>"""

    # Commentary section
    commentary_section = ""
    if commentary:
        commentary_section = f"""
        <div class="section">
            <h2>ARBITER'S COMMENTARY</h2>
            <blockquote class="commentary">{html.escape(commentary)}</blockquote>
        </div>"""

    # Score tier label
    score = scorecard.total_score
    if score >= 9:
        tier, tier_class = "EXCEPTIONAL", "tier-exceptional"
    elif score >= 7:
        tier, tier_class = "STRONG", "tier-strong"
    elif score >= 5:
        tier, tier_class = "SOLID", "tier-solid"
    else:
        tier, tier_class = "DEVELOPING", "tier-developing"

    from datetime import datetime
    scored_date = datetime.fromtimestamp(scorecard.scored_at).strftime("%B %d, %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Report Card — {html.escape(scorecard.team_name)}</title>
<style>
  @media print {{
    @page {{ size: A4; margin: 1.5cm; }}
    body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .no-print {{ display: none; }}
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
    background: #0a0e1a;
    color: #e0e0f0;
    padding: 2rem;
    max-width: 800px;
    margin: 0 auto;
  }}
  .header {{
    text-align: center;
    padding-bottom: 1.5rem;
    border-bottom: 2px solid #1a2040;
    margin-bottom: 2rem;
  }}
  .header h1 {{
    font-size: 0.75rem;
    letter-spacing: 0.3em;
    color: #00ff88;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
  }}
  .team-name {{
    font-size: 2rem;
    font-weight: 900;
    letter-spacing: 0.1em;
    color: #fff;
    text-transform: uppercase;
  }}
  .track-badge {{
    display: inline-block;
    margin-top: 0.5rem;
    padding: 0.25rem 0.75rem;
    border: 1px solid #00ccff40;
    color: #00ccff;
    font-size: 0.75rem;
    letter-spacing: 0.2em;
  }}
  .total-score-section {{
    text-align: center;
    padding: 2rem 0;
  }}
  .total-score {{
    font-size: 5rem;
    font-weight: 900;
    color: #00ff88;
    text-shadow: 0 0 30px rgba(0,255,136,0.3);
    line-height: 1;
  }}
  .total-score span {{ font-size: 1.5rem; color: #4a5080; }}
  .tier {{ font-size: 0.85rem; letter-spacing: 0.3em; margin-top: 0.5rem; }}
  .tier-exceptional {{ color: #ffd700; }}
  .tier-strong {{ color: #00ff88; }}
  .tier-solid {{ color: #00ccff; }}
  .tier-developing {{ color: #ff8844; }}
  .section {{ margin-bottom: 2rem; }}
  .section h2 {{
    font-size: 0.7rem;
    letter-spacing: 0.3em;
    color: #4a5080;
    margin-bottom: 1rem;
    text-transform: uppercase;
  }}
  table {{ width: 100%; border-collapse: collapse; }}
  .criterion-name {{ text-align: left; padding: 0.5rem 0; font-size: 0.85rem; }}
  .criterion-weight {{ text-align: center; color: #4a5080; font-size: 0.75rem; width: 3rem; }}
  .criterion-score {{ text-align: right; width: 45%; }}
  .score-bar-bg {{
    display: inline-block;
    width: calc(100% - 3rem);
    height: 6px;
    background: #1a2040;
    border-radius: 3px;
    vertical-align: middle;
  }}
  .score-bar {{
    height: 100%;
    background: linear-gradient(90deg, #00ccff, #00ff88);
    border-radius: 3px;
  }}
  .bonus-bar {{
    background: linear-gradient(90deg, #ffd700, #ff8844);
  }}
  .score-value {{
    display: inline-block;
    width: 2.5rem;
    text-align: right;
    font-weight: 700;
    font-size: 0.9rem;
  }}
  .score-value.bonus {{ color: #ffd700; }}
  .criterion-name.bonus {{ color: #ffd700; }}
  .justification-row .justification {{
    color: #6a7090;
    font-size: 0.7rem;
    padding: 0 0 0.75rem 0;
    font-style: italic;
  }}
  .commentary {{
    border-left: 3px solid #00ff8840;
    padding: 1rem 1.5rem;
    background: #0f1525;
    font-size: 0.85rem;
    line-height: 1.7;
    color: #b0b8d0;
    font-style: italic;
  }}
  .footer {{
    text-align: center;
    padding-top: 1.5rem;
    border-top: 1px solid #1a2040;
    color: #3a4060;
    font-size: 0.65rem;
    letter-spacing: 0.2em;
  }}
  .print-btn {{
    display: block;
    margin: 1rem auto;
    padding: 0.75rem 2rem;
    background: #00ff88;
    color: #0a0e1a;
    border: none;
    font-family: inherit;
    font-weight: 700;
    font-size: 0.85rem;
    letter-spacing: 0.1em;
    cursor: pointer;
    text-transform: uppercase;
  }}
  .print-btn:hover {{ background: #00cc6a; }}
</style>
</head>
<body>
<button class="print-btn no-print" onclick="window.print()">SAVE AS PDF</button>

<div class="header">
    <h1>NEBULA:FOG 2026 — AI Judge Report Card</h1>
    <div class="team-name">{html.escape(scorecard.team_name)}</div>
    <div class="track-badge">{html.escape(scorecard.track)}</div>
</div>

<div class="total-score-section">
    <div class="total-score">{scorecard.total_score:.1f}<span>/10</span></div>
    <div class="tier {tier_class}">{tier}</div>
</div>

<div class="section">
    <h2>SCORING BREAKDOWN</h2>
    <table>
        {criteria_rows}
        {bonus_html}
    </table>
</div>

{commentary_section}

<div class="footer">
    Evaluated by ARBITER — Autonomous AI Judge System — {scored_date}
</div>
</body>
</html>"""
