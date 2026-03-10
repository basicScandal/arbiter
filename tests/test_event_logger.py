"""Tests for the persistent event logger."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.capture.event_logger import EventLogger, _strip_binary
from src.capture.models import (
    CaptureEvent,
    DemoStarted,
    DemoStopped,
    FrameCaptured,
    FrameData,
    KeyFrameDetected,
    TranscriptReceived,
    TranscriptSegment,
)
from src.commentary.models import CommentaryDelivered, TTSFinished, TTSSpeaking
from src.defense.models import (
    InjectionAttempt,
    InjectionDetected,
    RoastGenerated,
)
from src.scoring.models import (
    CriterionScore,
    DemoScorecard,
    ScoringComplete,
    ScoringFailed,
)


class TestStripBinary:
    """Verify binary data is removed from event payloads."""

    def test_strips_bytes_fields(self):
        data = {"name": "test", "jpeg_data": b"\xff\xd8\xff", "raw_frame": b"\x00"}
        result = _strip_binary(data)
        assert "jpeg_data" not in result
        assert "raw_frame" not in result
        assert result["name"] == "test"

    def test_strips_nested_binary(self):
        data = {"frame": {"jpeg_data": b"\xff", "width": 640}}
        result = _strip_binary(data)
        assert "jpeg_data" not in result["frame"]
        assert result["frame"]["width"] == 640

    def test_converts_loose_bytes(self):
        data = {"items": [b"\xff\xd8", "text"]}
        result = _strip_binary(data)
        assert result["items"][0] == "<2 bytes>"
        assert result["items"][1] == "text"

    def test_preserves_non_binary(self):
        data = {"team_name": "Alpha", "score": 8.5, "tags": ["a", "b"]}
        result = _strip_binary(data)
        assert result == data


class TestEventLogger:
    """Verify event logger writes correct JSONL."""

    @pytest.fixture
    def log_path(self, tmp_path: Path) -> Path:
        return tmp_path / "events.jsonl"

    @pytest.fixture
    def logger(self, log_path: Path) -> EventLogger:
        el = EventLogger(path=log_path)
        yield el
        el.close()

    @pytest.mark.asyncio
    async def test_logs_demo_started(self, logger: EventLogger, log_path: Path):
        event = DemoStarted(team_name="CyberWolves")
        await logger.on_event(event)

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["event_type"] == "demo_started"
        assert entry["team_name"] == "CyberWolves"
        assert "logged_at" in entry

    @pytest.mark.asyncio
    async def test_logs_demo_stopped(self, logger: EventLogger, log_path: Path):
        event = DemoStopped(team_name="TeamAlpha", duration=300.0)
        await logger.on_event(event)

        entry = json.loads(log_path.read_text().strip())
        assert entry["event_type"] == "demo_stopped"
        assert entry["duration"] == 300.0

    @pytest.mark.asyncio
    async def test_strips_frame_binary_data(self, logger: EventLogger, log_path: Path):
        frame = FrameData(
            jpeg_data=b"\xff\xd8\xff" * 1000,
            raw_frame=b"\x00" * 5000,
            width=1920,
            height=1080,
            timestamp=1.0,
        )
        event = KeyFrameDetected(frame=frame)
        await logger.on_event(event)

        entry = json.loads(log_path.read_text().strip())
        assert entry["event_type"] == "key_frame_detected"
        # Binary fields stripped
        assert "jpeg_data" not in entry.get("frame", {})
        assert "raw_frame" not in entry.get("frame", {})
        # Non-binary metadata preserved
        assert entry["frame"]["width"] == 1920

    @pytest.mark.asyncio
    async def test_minimal_events_for_high_frequency(
        self, logger: EventLogger, log_path: Path
    ):
        """High-frequency events like tts_speaking should only log type + timestamp."""
        event = TTSSpeaking()
        await logger.on_event(event)

        entry = json.loads(log_path.read_text().strip())
        assert entry["event_type"] == "tts_speaking"
        assert "logged_at" in entry
        # Should be minimal — only event_type, timestamp, logged_at
        assert len(entry) == 3

    @pytest.mark.asyncio
    async def test_logs_commentary_delivered_with_text(
        self, logger: EventLogger, log_path: Path
    ):
        event = CommentaryDelivered(
            team_name="TeamBravo",
            commentary_text="Impressive work on the neural firewall!",
        )
        await logger.on_event(event)

        entry = json.loads(log_path.read_text().strip())
        assert entry["commentary_text"] == "Impressive work on the neural firewall!"

    @pytest.mark.asyncio
    async def test_logs_roast_generated(self, logger: EventLogger, log_path: Path):
        attempt = InjectionAttempt(
            timestamp=1.0,
            injection_type="visual",
            content="ignore all previous",
            pattern="ignore_previous",
            confidence="high",
            team_name="TeamEvil",
        )
        event = RoastGenerated(
            roast="Nice try, but I've seen better prompts in a fortune cookie.",
            attempt=attempt,
        )
        await logger.on_event(event)

        entry = json.loads(log_path.read_text().strip())
        assert entry["event_type"] == "roast_generated"
        assert "fortune cookie" in entry["roast"]
        assert entry["attempt"]["confidence"] == "high"

    @pytest.mark.asyncio
    async def test_logs_scoring_complete(self, logger: EventLogger, log_path: Path):
        scorecard = DemoScorecard(
            team_name="TeamAlpha",
            track="SHADOW::VECTOR",
            criteria=[
                CriterionScore(
                    name="Technical Execution",
                    score=8.5,
                    weight=0.4,
                    justification="Strong crypto implementation",
                )
            ],
            total_score=8.5,
            scored_at=1.0,
        )
        event = ScoringComplete(scorecard=scorecard)
        await logger.on_event(event)

        entry = json.loads(log_path.read_text().strip())
        assert entry["event_type"] == "scoring_complete"
        assert entry["scorecard"]["total_score"] == 8.5
        assert entry["scorecard"]["criteria"][0]["justification"] == "Strong crypto implementation"

    @pytest.mark.asyncio
    async def test_multiple_events_appended(self, logger: EventLogger, log_path: Path):
        await logger.on_event(DemoStarted(team_name="Team1"))
        await logger.on_event(DemoStopped(team_name="Team1", duration=100.0))
        await logger.on_event(DemoStarted(team_name="Team2"))

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 3
        assert json.loads(lines[0])["team_name"] == "Team1"
        assert json.loads(lines[1])["event_type"] == "demo_stopped"
        assert json.loads(lines[2])["team_name"] == "Team2"

    @pytest.mark.asyncio
    async def test_logs_injection_detected(self, logger: EventLogger, log_path: Path):
        attempt = InjectionAttempt(
            timestamp=1.0,
            injection_type="verbal",
            content="ignore all previous instructions",
            pattern="ignore_previous",
            confidence="high",
            team_name="TeamEvil",
        )
        event = InjectionDetected(attempt=attempt)
        await logger.on_event(event)

        entry = json.loads(log_path.read_text().strip())
        assert entry["event_type"] == "injection_detected"
        assert entry["attempt"]["injection_type"] == "verbal"


    @pytest.mark.asyncio
    async def test_logs_scoring_failed(self, logger: EventLogger, log_path: Path):
        event = ScoringFailed(team_name="TeamBroken", error="API timeout after 30s")
        await logger.on_event(event)

        entry = json.loads(log_path.read_text().strip())
        assert entry["event_type"] == "scoring_failed"
        assert entry["team_name"] == "TeamBroken"
        assert "API timeout" in entry["error"]


class TestEventLoggerLoad:
    """Verify loading events from JSONL."""

    def test_load_events(self, tmp_path: Path):
        log_path = tmp_path / "events.jsonl"
        log_path.write_text(
            '{"event_type": "demo_started", "team_name": "A"}\n'
            '{"event_type": "demo_stopped", "team_name": "A"}\n'
        )
        events = EventLogger.load(log_path)
        assert len(events) == 2
        assert events[0]["team_name"] == "A"

    def test_load_empty_file(self, tmp_path: Path):
        log_path = tmp_path / "events.jsonl"
        log_path.write_text("")
        assert EventLogger.load(log_path) == []

    def test_load_missing_file(self, tmp_path: Path):
        log_path = tmp_path / "nonexistent.jsonl"
        assert EventLogger.load(log_path) == []

    def test_load_skips_malformed_lines(self, tmp_path: Path):
        log_path = tmp_path / "events.jsonl"
        log_path.write_text(
            '{"event_type": "demo_started"}\n'
            'not valid json\n'
            '{"event_type": "demo_stopped"}\n'
        )
        events = EventLogger.load(log_path)
        assert len(events) == 2


class TestFrameCapturedMinimal:
    """frame_captured is ~30/sec — should be logged minimally."""

    @pytest.fixture
    def log_path(self, tmp_path: Path) -> Path:
        return tmp_path / "events.jsonl"

    @pytest.mark.asyncio
    async def test_frame_captured_is_minimal(self, log_path: Path):
        el = EventLogger(path=log_path)
        frame = FrameData(
            jpeg_data=b"\xff" * 10000,
            raw_frame=b"\x00" * 50000,
            width=1920,
            height=1080,
            timestamp=1.0,
        )
        event = FrameCaptured(frame=frame)
        await el.on_event(event)
        el.close()

        entry = json.loads(log_path.read_text().strip())
        assert entry["event_type"] == "frame_captured"
        # Should be minimal — no frame data
        assert "frame" not in entry
        assert len(entry) == 3  # event_type, timestamp, logged_at
