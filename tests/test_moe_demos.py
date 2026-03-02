"""MoE scoring test suite using real NEBULA:FOG:PRIME demo descriptions.

Scores the top 5 most-viewed demos from the NEBULA:FOG YouTube channel
through the full MoE pipeline (multi-provider scoring + commentary enrichment).

Source: https://www.youtube.com/@NEBULAFOG
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

# Load env before anything else
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from src.commentary.enricher import CommentaryEnricher
from src.commentary.models import Commentary
from src.defense.models import SanitizedOutput
from src.providers.factory import create_provider
from src.scoring.models import DemoScorecard
from src.scoring.moe_engine import MoEScoringEngine

# ---------------------------------------------------------------------------
# Test fixtures: Top 5 most-viewed NEBULA:FOG:PRIME demos
# ---------------------------------------------------------------------------

DEMOS: list[dict] = [
    {
        "team_name": "Nebula Investigations",
        "track": "ROGUE::AGENT",
        "views": 84,
        "duration": 510.0,  # 8:30
        "observations": [
            "Team presented Nebula Investigations, an AI-powered fraud liquidation investigation tool",
            "System analyzes images for ownership structures and generates relationship queries",
            "Data is organized in Neo4j graph database for complex relationship mapping",
            "Investigators can quickly search and explore complex documents",
            "Tool speeds up asset identification and data analysis for fraud cases",
            "Built by Kristin Del Rosso, Aashiq Ramachandran, and Jonathan De Armas",
        ],
        "transcripts": [
            "We built Nebula Investigations to simplify fraud liquidation investigations.",
            "The system takes images and documents, analyzes them for ownership structures, "
            "and generates relationship queries that get stored in Neo4j.",
            "This lets investigators quickly explore complex ownership networks "
            "and identify hidden assets much faster than manual analysis.",
        ],
    },
    {
        "team_name": "Revenge AI",
        "track": "SHADOW::VECTOR",
        "views": 75,
        "duration": 255.0,  # 4:15
        "observations": [
            "Ahmed Shosha of Stealthium presents Revenge AI, a hypervisor-based sandbox",
            "Tool is designed for reverse engineering and decompiling Windows executables",
            "Analyzes binaries extracting file size and import/export tables using Deepseek",
            "Attempts to convert assembly code into high-level C code",
            "Various LLMs tested including Llama for code decompilation",
            "Sandbox environment provides safe execution context for malware analysis",
        ],
        "transcripts": [
            "Revenge AI is a hypervisor-based sandbox for reverse engineering Windows executables.",
            "We extract details like file size and import-export tables, then use Deepseek "
            "to attempt converting assembly code into high-level C.",
            "We tested various LLMs including Llama to find the best model "
            "for accurate decompilation of binary code.",
        ],
    },
    {
        "team_name": "Privacy Impact Analyzer",
        "track": "ZERO::PROOF",
        "views": 48,
        "duration": 315.0,  # 5:15
        "observations": [
            "Tony UV introduces the Privacy Impact Analyzer for AI-driven privacy assessment",
            "Tool analyzes privacy impact assessments (PIAs) to identify common issues",
            "Identifies problems like data storage and consent management gaps",
            "Visualizes privacy problems across retail products",
            "Offers insights valuable to data privacy officers and CISOs",
            "Simplifies privacy analysis providing more efficient assessment workflow",
        ],
        "transcripts": [
            "The Privacy Impact Analyzer uses AI to analyze privacy impact assessments.",
            "It identifies common issues like data storage problems and consent management gaps, "
            "then visualizes these across retail products.",
            "This gives data privacy officers and CISOs actionable insights "
            "without having to manually read through hundreds of pages.",
        ],
    },
    {
        "team_name": "NextGen-SAST",
        "track": "SENTINEL::MESH",
        "views": 47,
        "duration": 779.0,  # 12:59
        "observations": [
            "Ian Klatzco, Joe Choi-Greene, and Mahesh Kukreja present NextGen-SAST",
            "Next-generation static analysis tool for security code review",
            "Demonstrated using the open-source Gruyere application as test target",
            "Integrates threat modeling and code scanning into one unified system",
            "Uses LLM-generated threat model combined with repo map and GitHub PR diff",
            "Tool automatically identifies security vulnerabilities in code changes",
        ],
        "transcripts": [
            "NextGen-SAST is a next-generation static analysis tool that integrates "
            "threat modeling and code scanning.",
            "We demonstrated it with Google's Gruyere app, showing how it uses "
            "an LLM-generated threat model, repo map, and GitHub PR diffs.",
            "The tool automatically identifies vulnerabilities by combining "
            "static analysis with AI-powered threat modeling.",
        ],
    },
    {
        "team_name": "Plan AI",
        "track": "ROGUE::AGENT",
        "views": 45,
        "duration": 377.0,  # 6:17
        "observations": [
            "Niels Provos, inventor of the term hackathon, showcases Plan AI",
            "Framework for automating curation and analysis of data breach reports",
            "System fetches relevant web resources and analyzes them with language models",
            "Produces summarized root cause analyses of security breaches",
            "Generates structured research plans for breach investigation",
            "Demonstrates automated security incident analysis pipeline",
        ],
        "transcripts": [
            "Plan AI automates the curation and analysis of data breach reports.",
            "The system fetches relevant web resources, analyzes them with language models, "
            "and produces summarized root cause analyses.",
            "It helps quickly generate structured research plans for investigating "
            "security incidents at scale.",
        ],
    },
]


def _build_providers() -> list:
    """Create available LLM providers from env vars."""
    providers = []
    gemini_key = os.getenv("GEMINI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPEN_API_KEY")

    if gemini_key:
        providers.append(create_provider("gemini", gemini_key))
    if anthropic_key:
        providers.append(create_provider("claude", anthropic_key))
    if openai_key:
        providers.append(create_provider("openai", openai_key))

    return providers


async def score_demo(engine: MoEScoringEngine, demo: dict) -> DemoScorecard:
    """Score a single demo through the MoE engine."""
    sanitized = SanitizedOutput(
        team_name=demo["team_name"],
        observations=demo["observations"],
        transcripts=demo["transcripts"],
        injection_attempts=[],
        demo_duration=demo["duration"],
    )
    return await engine.score(sanitized, demo["track"])


async def enrich_commentary(enricher: CommentaryEnricher, demo: dict) -> Commentary | None:
    """Generate and enrich mock commentary for a demo."""
    # Simulate Gemini's raw commentary style (flat, factual)
    raw_text = ". ".join(demo["observations"][:4]) + "."
    raw_sentences = demo["observations"][:4]

    original = Commentary(
        team_name=demo["team_name"],
        text=raw_text,
        sentences=raw_sentences,
        emotion_map={i: "neutral" for i in range(len(raw_sentences))},
        generated_at=time.time(),
    )

    return await enricher.enrich(original, demo["observations"])


async def main():
    print("\n" + "=" * 70)
    print("  NEBULA:FOG:PRIME — MoE Demo Scoring Suite")
    print("  Top 5 Most-Viewed Demos from youtube.com/@NEBULAFOG")
    print("=" * 70)

    providers = _build_providers()
    provider_names = [p.name for p in providers]
    print(f"\n  Providers: {', '.join(provider_names)} ({len(providers)} total)")

    if len(providers) < 1:
        print("  ERROR: No API keys configured. Set GEMINI_API_KEY / ANTHROPIC_API_KEY / OPEN_API_KEY")
        sys.exit(1)

    engine = MoEScoringEngine(providers=providers)

    # Set up enricher (prefer Claude, fallback to OpenAI)
    enricher = None
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        enricher = CommentaryEnricher(provider=create_provider("claude", anthropic_key))
        print("  Enrichment: Claude")
    else:
        print("  Enrichment: Disabled (no ANTHROPIC_API_KEY)")

    # Score all demos
    results: list[tuple[dict, DemoScorecard, Commentary | None]] = []

    for i, demo in enumerate(DEMOS, 1):
        print(f"\n  [{i}/{len(DEMOS)}] Scoring {demo['team_name']} ({demo['track']})...")
        t0 = time.time()

        scorecard = await score_demo(engine, demo)

        enriched = None
        if enricher:
            enriched = await enrich_commentary(enricher, demo)

        elapsed = time.time() - t0
        print(f"         Score: {scorecard.total_score}/10  ({elapsed:.1f}s)")

        results.append((demo, scorecard, enriched))

    # Print detailed results
    print("\n" + "=" * 70)
    print("  RESULTS — Ranked by MoE Score")
    print("=" * 70)

    # Sort by score descending
    results.sort(key=lambda r: r[1].total_score, reverse=True)

    for rank, (demo, scorecard, enriched) in enumerate(results, 1):
        print(f"\n  #{rank}  {scorecard.team_name}")
        print(f"       Track: {scorecard.track}  |  Views: {demo['views']}  |  Duration: {demo['duration']:.0f}s")
        print(f"       Total: {scorecard.total_score}/10")
        print(f"       Criteria:")
        for c in scorecard.criteria:
            print(f"         - {c.name}: {c.score}/10 (w={c.weight})")
            if c.justification:
                j = c.justification[:100]
                print(f"           {j}...")
        if scorecard.track_bonus:
            print(f"       Track Bonus ({scorecard.track_bonus.name}): {scorecard.track_bonus.score}/10")
        if enriched and enriched.text != ". ".join(demo["observations"][:4]) + ".":
            print(f"       Commentary ({len(enriched.text)} chars):")
            # Word-wrap the commentary
            words = enriched.text.split()
            line = "         "
            for w in words:
                if len(line) + len(w) + 1 > 90:
                    print(line)
                    line = "         " + w
                else:
                    line += " " + w if line.strip() else "         " + w
            if line.strip():
                print(line)

    # Summary table
    print("\n" + "=" * 70)
    print("  LEADERBOARD")
    print("  " + "-" * 66)
    print(f"  {'Rank':<6}{'Team':<30}{'Track':<18}{'Score':<8}{'Views'}")
    print("  " + "-" * 66)
    for rank, (demo, scorecard, _) in enumerate(results, 1):
        print(
            f"  {rank:<6}{scorecard.team_name:<30}{scorecard.track:<18}"
            f"{scorecard.total_score:<8}{demo['views']}"
        )
    print("  " + "-" * 66)

    # Export JSON for downstream use
    export = {
        "scored_at": time.time(),
        "providers": provider_names,
        "results": [
            {
                "rank": rank,
                "team_name": scorecard.team_name,
                "track": scorecard.track,
                "total_score": scorecard.total_score,
                "criteria": [
                    {"name": c.name, "score": c.score, "weight": c.weight}
                    for c in scorecard.criteria
                ],
                "track_bonus": (
                    {"name": scorecard.track_bonus.name, "score": scorecard.track_bonus.score}
                    if scorecard.track_bonus
                    else None
                ),
                "views": demo["views"],
                "duration": demo["duration"],
            }
            for rank, (demo, scorecard, _) in enumerate(results, 1)
        ],
    }

    export_path = os.path.join(os.path.dirname(__file__), "moe_demo_results.json")
    with open(export_path, "w") as f:
        json.dump(export, f, indent=2)
    print(f"\n  Results exported to {export_path}")

    print("\n" + "=" * 70)
    print("  Done.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
