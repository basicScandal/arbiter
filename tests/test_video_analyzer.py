"""Tests for VideoAnalyzer response parsing (no API calls or OpenCV needed)."""

from __future__ import annotations

import json

import pytest

from src.replay.config import VideoEntry
from src.replay.video_analyzer import AnalysisResult, VideoAnalyzer


@pytest.fixture
def entry() -> VideoEntry:
    return VideoEntry(1, "test", "TestTeam", "ROGUE::AGENT", "3:00")


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------


class TestParseResponse:
    """Tests for VideoAnalyzer._parse_response (static method)."""

    def test_valid_json(self, entry: VideoEntry):
        raw = json.dumps({
            "observations": ["obs1", "obs2"],
            "transcripts": ["seg1"],
            "demo_duration_seconds": 180,
            "tech_stack": ["Python", "React"],
            "one_line_summary": "A cool demo",
        })
        result = VideoAnalyzer._parse_response(raw, entry)
        assert isinstance(result, AnalysisResult)
        assert result.observations == ["obs1", "obs2"]
        assert result.transcripts == ["seg1"]
        assert result.duration_seconds == 180.0
        assert result.tech_stack == ["Python", "React"]
        assert result.summary == "A cool demo"

    def test_json_with_markdown_fences(self, entry: VideoEntry):
        """Claude often wraps JSON in ```json ... ``` fences."""
        inner = json.dumps({
            "observations": ["saw code"],
            "transcripts": [],
            "demo_duration_seconds": 60,
            "tech_stack": [],
            "one_line_summary": "Quick demo",
        })
        raw = f"```json\n{inner}\n```"
        result = VideoAnalyzer._parse_response(raw, entry)
        assert result.observations == ["saw code"]
        assert result.summary == "Quick demo"

    def test_json_with_bare_fences(self, entry: VideoEntry):
        """Handles ``` without json language tag."""
        inner = json.dumps({
            "observations": ["item"],
            "transcripts": [],
            "demo_duration_seconds": 30,
            "tech_stack": ["Go"],
            "one_line_summary": "Fast demo",
        })
        raw = f"```\n{inner}\n```"
        result = VideoAnalyzer._parse_response(raw, entry)
        assert result.observations == ["item"]

    def test_missing_fields_use_defaults(self, entry: VideoEntry):
        """Missing JSON keys fall back to defaults."""
        raw = json.dumps({})
        result = VideoAnalyzer._parse_response(raw, entry)
        assert result.observations == []
        assert result.transcripts == []
        assert result.duration_seconds == 180.0  # fallback to entry duration
        assert result.tech_stack == []
        assert result.summary == "Demo by TestTeam"

    def test_invalid_json_raises(self, entry: VideoEntry):
        with pytest.raises(ValueError, match="Could not parse response as JSON"):
            VideoAnalyzer._parse_response("not json at all", entry)

    def test_partial_fields(self, entry: VideoEntry):
        """Some fields present, others missing."""
        raw = json.dumps({
            "observations": ["only obs"],
            "tech_stack": ["Rust"],
        })
        result = VideoAnalyzer._parse_response(raw, entry)
        assert result.observations == ["only obs"]
        assert result.tech_stack == ["Rust"]
        assert result.transcripts == []
        assert result.summary == "Demo by TestTeam"


# ---------------------------------------------------------------------------
# AnalysisResult
# ---------------------------------------------------------------------------


class TestAnalysisResult:
    def test_slots(self):
        result = AnalysisResult(
            observations=["a"],
            transcripts=["b"],
            duration_seconds=60.0,
            tech_stack=["Python"],
            summary="Test",
        )
        assert result.observations == ["a"]
        assert result.transcripts == ["b"]
        assert result.duration_seconds == 60.0
        assert result.tech_stack == ["Python"]
        assert result.summary == "Test"

    def test_uses_slots(self):
        """AnalysisResult uses __slots__ for memory efficiency."""
        assert hasattr(AnalysisResult, "__slots__")
        result = AnalysisResult([], [], 0.0, [], "")
        with pytest.raises(AttributeError):
            result.nonexistent_attr = "boom"
