"""Async wrapper around yt-dlp for downloading demo videos."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from src.replay.config import VIDEOS_DIR, VideoEntry, youtube_url

logger = logging.getLogger(__name__)


async def download_video(entry: VideoEntry, output_dir: Path = VIDEOS_DIR) -> Path | None:
    """Download a single video at 720p. Returns path if successful, None on failure.

    Skips download if the file already exists on disk (cache hit).
    Uses yt-dlp as a subprocess for reliability and to avoid holding the event loop.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{entry.video_id}.mp4"

    if output_path.exists() and output_path.stat().st_size > 0:
        logger.info("[%d/%s] Cached: %s", entry.number, entry.team_name, output_path.name)
        return output_path

    url = youtube_url(entry)
    logger.info("[%d/%s] Downloading %s ...", entry.number, entry.team_name, url)

    cmd = [
        "yt-dlp",
        "--format", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--output", str(output_path),
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        url,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

        if proc.returncode != 0:
            err_msg = stderr.decode().strip() if stderr else "unknown error"
            logger.error(
                "[%d/%s] Download failed (rc=%d): %s",
                entry.number, entry.team_name, proc.returncode, err_msg,
            )
            return None

        size_mb = output_path.stat().st_size / 1024 / 1024
        logger.info(
            "[%d/%s] Downloaded: %s (%.1f MB)",
            entry.number, entry.team_name, output_path.name, size_mb,
        )
        return output_path

    except asyncio.TimeoutError:
        logger.error("[%d/%s] Download timed out after 300s", entry.number, entry.team_name)
        return None
    except FileNotFoundError:
        logger.error("yt-dlp not found. Install with: uv add --dev yt-dlp")
        return None


async def download_all(
    entries: list[VideoEntry], output_dir: Path = VIDEOS_DIR,
) -> dict[int, Path]:
    """Download all videos sequentially. Returns {video_number: path} for successes."""
    results: dict[int, Path] = {}
    for entry in entries:
        path = await download_video(entry, output_dir)
        if path is not None:
            results[entry.number] = path
    logger.info("Downloaded %d/%d videos", len(results), len(entries))
    return results
