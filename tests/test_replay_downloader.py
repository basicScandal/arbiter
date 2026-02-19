"""Tests for the async yt-dlp video downloader."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.replay.config import VideoEntry
from src.replay.downloader import download_all, download_video


@pytest.fixture
def entry() -> VideoEntry:
    return VideoEntry(1, "test_vid", "TestTeam", "ROGUE::AGENT", "3:00")


# ---------------------------------------------------------------------------
# download_video
# ---------------------------------------------------------------------------


class TestDownloadVideo:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_existing_file(self, tmp_path: Path, entry: VideoEntry):
        """When a video file already exists, skip download and return path."""
        video_file = tmp_path / f"{entry.video_id}.mp4"
        video_file.write_bytes(b"fake video data")

        result = await download_video(entry, output_dir=tmp_path)
        assert result == video_file

    @pytest.mark.asyncio
    async def test_cache_hit_skips_empty_file(self, tmp_path: Path, entry: VideoEntry):
        """Empty files should NOT count as a cache hit."""
        video_file = tmp_path / f"{entry.video_id}.mp4"
        video_file.write_bytes(b"")

        with patch("src.replay.downloader.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            # The file is empty, so it should attempt download
            # The subprocess mock returns rc=0 but file is still empty,
            # which will cause stat().st_size to access the empty file
            await download_video(entry, output_dir=tmp_path)
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_download(self, tmp_path: Path, entry: VideoEntry):
        """Successful yt-dlp subprocess returns the output path."""
        video_file = tmp_path / f"{entry.video_id}.mp4"

        with patch("src.replay.downloader.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            # Write a non-empty file to simulate yt-dlp output
            video_file.write_bytes(b"video content here")

            result = await download_video(entry, output_dir=tmp_path)
            assert result == video_file

    @pytest.mark.asyncio
    async def test_failed_download_returns_none(self, tmp_path: Path, entry: VideoEntry):
        """Non-zero return code from yt-dlp returns None."""
        with patch("src.replay.downloader.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b"download error"))
            mock_proc.returncode = 1
            mock_exec.return_value = mock_proc

            result = await download_video(entry, output_dir=tmp_path)
            assert result is None

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self, tmp_path: Path, entry: VideoEntry):
        """Subprocess timeout returns None."""
        with patch("src.replay.downloader.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
            mock_exec.return_value = mock_proc

            result = await download_video(entry, output_dir=tmp_path)
            assert result is None

    @pytest.mark.asyncio
    async def test_ytdlp_not_found_returns_none(self, tmp_path: Path, entry: VideoEntry):
        """FileNotFoundError (yt-dlp not installed) returns None."""
        with patch(
            "src.replay.downloader.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError,
        ):
            result = await download_video(entry, output_dir=tmp_path)
            assert result is None

    @pytest.mark.asyncio
    async def test_creates_output_directory(self, tmp_path: Path, entry: VideoEntry):
        """Output directory is created if it doesn't exist."""
        nested_dir = tmp_path / "sub" / "dir"
        assert not nested_dir.exists()

        with patch("src.replay.downloader.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
            mock_proc.returncode = 1
            mock_exec.return_value = mock_proc

            await download_video(entry, output_dir=nested_dir)
            assert nested_dir.exists()


# ---------------------------------------------------------------------------
# download_all
# ---------------------------------------------------------------------------


class TestDownloadAll:
    @pytest.mark.asyncio
    async def test_returns_successful_downloads(self, tmp_path: Path):
        """Only includes entries where download succeeded."""
        entries = [
            VideoEntry(1, "vid1", "Team1", "TR", "1:00"),
            VideoEntry(2, "vid2", "Team2", "TR", "2:00"),
            VideoEntry(3, "vid3", "Team3", "TR", "3:00"),
        ]

        # Pre-cache vid1 and vid3, vid2 will fail
        (tmp_path / "vid1.mp4").write_bytes(b"cached1")
        (tmp_path / "vid3.mp4").write_bytes(b"cached3")

        with patch("src.replay.downloader.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
            mock_proc.returncode = 1
            mock_exec.return_value = mock_proc

            results = await download_all(entries, output_dir=tmp_path)

        assert 1 in results
        assert 3 in results
        assert 2 not in results

    @pytest.mark.asyncio
    async def test_empty_entries_returns_empty(self, tmp_path: Path):
        results = await download_all([], output_dir=tmp_path)
        assert results == {}
