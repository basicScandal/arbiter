"""Video manifest and replay configuration for NEBULA:FOG:PRIME demos."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoEntry:
    """A single demo video with metadata."""

    number: int
    video_id: str
    team_name: str
    track: str
    duration: str  # Human-readable "M:SS"


# 15 NEBULA:FOG:PRIME (Jan 2025) demos from @NEBULAFOG YouTube channel
MANIFEST: list[VideoEntry] = [
    VideoEntry(1, "CgnDgSnO_Lo", "Source Code Review Agent", "ROGUE::AGENT", "6:46"),
    VideoEntry(2, "Hyu6Rln21K0", "AI Vulnerability Triage", "SENTINEL::MESH", "3:02"),
    VideoEntry(3, "AANOeo56KPc", "Private Computer Use", "SHADOW::VECTOR", "6:02"),
    VideoEntry(4, "o48IxJOeMfQ", "Fake Content Generation", "ROGUE::AGENT", "4:40"),
    VideoEntry(5, "5Inctca6grA", "Nebula Investigations", "SENTINEL::MESH", "8:30"),
    VideoEntry(6, "gQNG_zq2dNc", "Walmart 2", "ROGUE::AGENT", "4:38"),
    VideoEntry(7, "myiMib1VE1Q", "NextGen SAST", "SENTINEL::MESH", "12:59"),
    VideoEntry(8, "Zv6mtk94l7s", "Privacy Impact Analyzer", "SHADOW::VECTOR", "5:15"),
    VideoEntry(9, "Z0rYTioqRyY", "Nebula Fog Subprime", "ROGUE::AGENT", "3:58"),
    VideoEntry(10, "CmGBcdWvZTQ", "Plan AI", "ROGUE::AGENT", "6:17"),
    VideoEntry(11, "KH41wLOgKq8", "Advanced Security Tool", "SENTINEL::MESH", "12:39"),
    VideoEntry(12, "kt2-ZxYKRDM", "Web App Security Testing", "SENTINEL::MESH", "5:05"),
    VideoEntry(13, "VVrWaBagg4c", "LAMP Monitoring Platform", "SENTINEL::MESH", "7:21"),
    VideoEntry(14, "VbUOfuFj84c", "AI Cloud Security Analysis", "SENTINEL::MESH", "3:08"),
    VideoEntry(15, "x24iFJy8zVk", "Revenge AI", "ROGUE::AGENT", "4:15"),
]


def duration_seconds(entry: VideoEntry) -> float:
    """Parse 'M:SS' duration string to seconds."""
    parts = entry.duration.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def youtube_url(entry: VideoEntry) -> str:
    """Full YouTube URL for a video entry."""
    return f"https://www.youtube.com/watch?v={entry.video_id}"


# Output directory layout
BASE_DIR = Path("data/replay")
VIDEOS_DIR = BASE_DIR / "videos"
OBSERVATIONS_DIR = BASE_DIR / "observations"
SCORES_DIR = BASE_DIR / "scores"
COMMENTARY_DIR = BASE_DIR / "commentary"
DELIBERATION_DIR = BASE_DIR / "deliberation"
LOG_FILE = BASE_DIR / "replay.log"
