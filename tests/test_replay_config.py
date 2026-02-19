"""Tests for replay configuration, video manifest, and utility functions."""

from __future__ import annotations

import pytest

from src.replay.config import (
    MANIFEST,
    VideoEntry,
    duration_seconds,
    youtube_url,
)


# ---------------------------------------------------------------------------
# VideoEntry dataclass
# ---------------------------------------------------------------------------


class TestVideoEntry:
    def test_frozen_dataclass(self):
        entry = VideoEntry(1, "abc123", "Team", "TRACK", "3:45")
        with pytest.raises(AttributeError):
            entry.number = 99

    def test_fields(self):
        entry = VideoEntry(5, "vid_id", "My Team", "ROGUE::AGENT", "12:59")
        assert entry.number == 5
        assert entry.video_id == "vid_id"
        assert entry.team_name == "My Team"
        assert entry.track == "ROGUE::AGENT"
        assert entry.duration == "12:59"


# ---------------------------------------------------------------------------
# duration_seconds
# ---------------------------------------------------------------------------


class TestDurationSeconds:
    def test_simple_duration(self):
        entry = VideoEntry(1, "x", "T", "TR", "3:02")
        assert duration_seconds(entry) == 182.0

    def test_zero_seconds(self):
        entry = VideoEntry(1, "x", "T", "TR", "5:00")
        assert duration_seconds(entry) == 300.0

    def test_double_digit_minutes(self):
        entry = VideoEntry(1, "x", "T", "TR", "12:59")
        assert duration_seconds(entry) == 779.0

    def test_zero_minutes(self):
        entry = VideoEntry(1, "x", "T", "TR", "0:30")
        assert duration_seconds(entry) == 30.0


# ---------------------------------------------------------------------------
# youtube_url
# ---------------------------------------------------------------------------


class TestYoutubeUrl:
    def test_url_format(self):
        entry = VideoEntry(1, "CgnDgSnO_Lo", "Team", "TR", "6:46")
        assert youtube_url(entry) == "https://www.youtube.com/watch?v=CgnDgSnO_Lo"

    def test_url_with_different_id(self):
        entry = VideoEntry(1, "abc-123_XY", "Team", "TR", "1:00")
        assert youtube_url(entry) == "https://www.youtube.com/watch?v=abc-123_XY"


# ---------------------------------------------------------------------------
# MANIFEST
# ---------------------------------------------------------------------------


class TestManifest:
    def test_manifest_has_15_entries(self):
        assert len(MANIFEST) == 15

    def test_manifest_numbers_sequential(self):
        numbers = [e.number for e in MANIFEST]
        assert numbers == list(range(1, 16))

    def test_all_entries_have_video_ids(self):
        for entry in MANIFEST:
            assert entry.video_id, f"Entry {entry.number} missing video_id"

    def test_all_entries_have_team_names(self):
        for entry in MANIFEST:
            assert entry.team_name, f"Entry {entry.number} missing team_name"

    def test_all_durations_parseable(self):
        for entry in MANIFEST:
            secs = duration_seconds(entry)
            assert secs > 0, f"Entry {entry.number} has non-positive duration"
