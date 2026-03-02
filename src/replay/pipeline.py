"""Replay pipeline orchestrator: download → analyze → score → save → deliberate."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from src.commentary.generator import CommentaryGenerator
from src.commentary.models import Commentary
from src.defense.models import SanitizedOutput
from src.logging_config import configure_logging
from src.memory.deliberation_engine import DeliberationEngine
from src.memory.models import DeliberationResult, DemoMemory
from src.memory.store import MemoryStore
from src.replay.config import (
    BASE_DIR,
    COMMENTARY_DIR,
    DELIBERATION_DIR,
    LOG_FILE,
    MANIFEST,
    OBSERVATIONS_DIR,
    SCORES_DIR,
    VIDEOS_DIR,
    VideoEntry,
)
from src.replay.downloader import download_all
from src.replay.video_analyzer import VideoAnalyzer
from src.resilience.circuit_breaker import GeminiCircuitBreaker
from src.scoring.engine import ScoringEngine
from src.scoring.models import DemoScorecard
from src.scoring.store import ScoreStore
from src.utils import sanitize_team_name

logger = logging.getLogger(__name__)


class ReplayPipeline:
    """Orchestrates the full batch replay: download, analyze, score, deliberate, report."""

    def __init__(self) -> None:
        load_dotenv()
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY required. Set it in .env or environment."
            )
        groq_key = os.environ.get("GROQ_API_KEY", "")

        # Shared circuit breaker -- once Gemini daily quota is exhausted,
        # all components skip Gemini and go straight to fallback providers
        self._circuit_breaker = GeminiCircuitBreaker()

        self._analyzer = VideoAnalyzer()  # Uses ANTHROPIC_API_KEY from env
        self._scorer = ScoringEngine(api_key, circuit_breaker=self._circuit_breaker)
        self._commentator = CommentaryGenerator(api_key, groq_api_key=groq_key, circuit_breaker=self._circuit_breaker)
        self._deliberator = DeliberationEngine(api_key, circuit_breaker=self._circuit_breaker)
        self._score_store = ScoreStore(scores_dir=str(SCORES_DIR))
        self._memory_store = MemoryStore(observations_dir=str(OBSERVATIONS_DIR))

        # Ensure output directories
        for d in [BASE_DIR, VIDEOS_DIR, OBSERVATIONS_DIR, SCORES_DIR, COMMENTARY_DIR, DELIBERATION_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        *,
        skip_download: bool = False,
        start: int = 1,
        only: int | None = None,
        force: bool = False,
    ) -> None:
        """Run the full replay pipeline.

        Args:
            skip_download: If True, skip video downloads (use cached files).
            start: Resume from this video number (1-indexed).
            only: If set, process only this video number.
            force: If True, re-process all demos even if results exist.
        """
        configure_logging(console=True, log_file=str(LOG_FILE))
        t0 = time.time()

        entries = self._select_entries(start=start, only=only)
        logger.info(
            "Replay pipeline starting: %d video(s), skip_download=%s, force=%s",
            len(entries), skip_download, force,
        )

        # Phase 1: Download
        video_paths: dict[int, Path] = {}
        if not skip_download:
            logger.info("=== Phase 1: Downloading videos ===")
            video_paths = await download_all(entries, VIDEOS_DIR)
        else:
            logger.info("=== Phase 1: Skipping downloads (using cache) ===")
            for entry in entries:
                cached = VIDEOS_DIR / f"{entry.video_id}.mp4"
                if cached.exists():
                    video_paths[entry.number] = cached
                else:
                    logger.warning(
                        "[%d/%s] No cached video found, skipping",
                        entry.number, entry.team_name,
                    )

        # Phase 2: Per-demo analysis + scoring
        logger.info("=== Phase 2: Analyzing and scoring %d demos ===", len(video_paths))
        succeeded = 0
        failed = 0
        cached = 0
        for entry in entries:
            if entry.number not in video_paths:
                logger.warning("[%d/%s] No video available, skipping", entry.number, entry.team_name)
                failed += 1
                continue

            # Result caching: skip if score + memory already exist
            if not force and self._has_cached_results(entry.team_name):
                logger.info(
                    "[%d/%s] Cached results found, skipping (use --force to re-process)",
                    entry.number, entry.team_name,
                )
                cached += 1
                succeeded += 1
                continue

            try:
                await self._process_demo(entry, video_paths[entry.number])
                succeeded += 1
            except Exception:
                logger.exception("[%d/%s] Processing failed, skipping", entry.number, entry.team_name)
                failed += 1

        logger.info(
            "Phase 2 complete: %d succeeded (%d cached), %d failed",
            succeeded, cached, failed,
        )

        # Phase 3: Deliberation (if >1 demo succeeded)
        if succeeded >= 2:
            logger.info("=== Phase 3: Deliberation ===")
            try:
                result = await self._deliberate()
                logger.info("Deliberation complete: %d teams ranked", len(result.rankings))
            except Exception:
                logger.exception("Deliberation failed")
        elif succeeded == 1:
            logger.info("Skipping deliberation (only 1 demo succeeded)")
        else:
            logger.warning("No demos succeeded, skipping deliberation")

        # Phase 4: Report
        logger.info("=== Phase 4: Generating reports ===")
        from src.replay.report import generate_report
        await generate_report()

        elapsed = time.time() - t0
        logger.info("Pipeline complete in %.1f minutes", elapsed / 60)

    def _has_cached_results(self, team_name: str) -> bool:
        """Check if score and memory files already exist for this team."""
        sanitized = sanitize_team_name(team_name)
        score_path = SCORES_DIR / f"{sanitized}.json"
        memory_path = OBSERVATIONS_DIR / f"{sanitized}.json"
        return score_path.exists() and memory_path.exists()

    async def _process_demo(self, entry: VideoEntry, video_path: Path) -> None:
        """Process a single demo: analyze → build SanitizedOutput → score → save."""
        logger.info(
            "[%d/%s] Processing (track=%s) ...",
            entry.number, entry.team_name, entry.track,
        )

        # Analyze video via Claude vision (frame extraction)
        analysis = await self._analyzer.analyze(str(video_path), entry)

        # Build SanitizedOutput (bridge to existing scoring infrastructure)
        sanitized = SanitizedOutput(
            team_name=entry.team_name,
            observations=analysis.observations,
            transcripts=analysis.transcripts,
            injection_attempts=[],  # Replay videos have no live injection attempts
            demo_duration=analysis.duration_seconds,
        )

        # Score
        scorecard: DemoScorecard = await self._scorer.score(sanitized, entry.track)
        await self._score_store.save(scorecard)
        logger.info(
            "[%d/%s] Scored: %.1f", entry.number, entry.team_name, scorecard.total_score,
        )

        # Commentary
        commentary: Commentary = await self._commentator.generate(sanitized)
        await self._save_commentary(commentary)
        logger.info("[%d/%s] Commentary generated", entry.number, entry.team_name)

        # Memory (for deliberation)
        memory = DemoMemory(
            team_name=entry.team_name,
            track=entry.track,
            observations=analysis.observations,
            transcripts=analysis.transcripts,
            injection_attempts=0,
            demo_duration=analysis.duration_seconds,
            stored_at=time.time(),
        )
        await self._memory_store.save(memory)
        logger.info("[%d/%s] Memory saved", entry.number, entry.team_name)

    async def _deliberate(self) -> DeliberationResult:
        """Run deliberation across all saved demos."""
        memories = await self._memory_store.load_all()
        scorecards = await self._score_store.load_all()

        result = await self._deliberator.deliberate(memories, scorecards)

        # Save deliberation result
        DELIBERATION_DIR.mkdir(parents=True, exist_ok=True)
        result_path = DELIBERATION_DIR / "result.json"
        data = json.dumps(result.model_dump(), indent=2, default=str)
        await asyncio.to_thread(result_path.write_text, data)
        logger.info("Deliberation saved to %s", result_path)

        return result

    async def _save_commentary(self, commentary: Commentary) -> Path:
        """Save commentary JSON to the commentary directory."""
        COMMENTARY_DIR.mkdir(parents=True, exist_ok=True)
        name = commentary.team_name.replace(" ", "_").lower()
        name = "".join(c for c in name if c.isalnum() or c in "_-")
        path = COMMENTARY_DIR / f"{name}.json"
        data = json.dumps(commentary.model_dump(), indent=2, default=str)
        await asyncio.to_thread(path.write_text, data)
        return path

    @staticmethod
    def _select_entries(
        *, start: int = 1, only: int | None = None,
    ) -> list[VideoEntry]:
        """Filter manifest entries based on CLI flags."""
        if only is not None:
            return [e for e in MANIFEST if e.number == only]
        return [e for e in MANIFEST if e.number >= start]

