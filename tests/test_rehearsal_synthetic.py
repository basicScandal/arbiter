"""Tests for synthetic capture event injection."""

from __future__ import annotations

import asyncio

import pytest

from src.capture.event_bus import EventBus
from src.rehearsal.synthetic_capture import SyntheticCapture, _SYNTHETIC_TRANSCRIPTS, _make_synthetic_frame
from tests.helpers.event_collector import EventCollector


# ---------------------------------------------------------------------------
# _make_synthetic_frame helper
# ---------------------------------------------------------------------------


class TestMakeSyntheticFrame:
    def test_returns_valid_frame_data(self):
        frame = _make_synthetic_frame()
        assert frame.jpeg_data[:2] == b"\xff\xd8"  # JPEG magic bytes
        assert frame.width == 1
        assert frame.height == 1
        assert frame.is_key_frame is True
        assert frame.timestamp > 0


# ---------------------------------------------------------------------------
# SyntheticCapture event sequence
# ---------------------------------------------------------------------------


class TestSyntheticCapture:
    @pytest.mark.asyncio
    async def test_publishes_demo_started(self, event_bus: EventBus):
        collector = EventCollector(event_bus)
        capture = SyntheticCapture(event_bus)

        await capture.run_demo(team_name="TestTeam", track="SENTINEL::MESH")

        # Yield to let event tasks complete
        await asyncio.sleep(0.1)

        started = collector.of_type("demo_started")
        assert len(started) == 1
        assert started[0].team_name == "TestTeam"

    @pytest.mark.asyncio
    async def test_publishes_three_key_frames(self, event_bus: EventBus):
        collector = EventCollector(event_bus)
        capture = SyntheticCapture(event_bus)

        await capture.run_demo()
        await asyncio.sleep(0.1)

        frames = collector.of_type("key_frame_detected")
        assert len(frames) == 3
        for kf in frames:
            assert kf.frame.is_key_frame is True
            assert kf.frame.jpeg_data[:2] == b"\xff\xd8"

    @pytest.mark.asyncio
    async def test_publishes_three_transcripts(self, event_bus: EventBus):
        collector = EventCollector(event_bus)
        capture = SyntheticCapture(event_bus)

        await capture.run_demo()
        await asyncio.sleep(0.1)

        transcripts = collector.of_type("transcript_received")
        assert len(transcripts) == 3
        for t in transcripts:
            assert t.segment.text
            assert t.segment.is_final is True

    @pytest.mark.asyncio
    async def test_publishes_demo_stopped(self, event_bus: EventBus):
        collector = EventCollector(event_bus)
        capture = SyntheticCapture(event_bus)

        await capture.run_demo(team_name="FinalTeam", duration=300.0)
        await asyncio.sleep(0.1)

        stopped = collector.of_type("demo_stopped")
        assert len(stopped) == 1
        assert stopped[0].team_name == "FinalTeam"
        assert stopped[0].duration == 300.0

    @pytest.mark.asyncio
    async def test_event_order(self, event_bus: EventBus):
        """Events arrive in the correct order: start -> frames -> transcripts -> stop."""
        collector = EventCollector(event_bus)
        capture = SyntheticCapture(event_bus)

        await capture.run_demo()
        await asyncio.sleep(0.1)

        types = [e.event_type for e in collector.events]
        expected = [
            "demo_started",
            "key_frame_detected",
            "key_frame_detected",
            "key_frame_detected",
            "transcript_received",
            "transcript_received",
            "transcript_received",
            "demo_stopped",
        ]
        assert types == expected

    @pytest.mark.asyncio
    async def test_default_team_name(self, event_bus: EventBus):
        collector = EventCollector(event_bus)
        capture = SyntheticCapture(event_bus)

        await capture.run_demo()
        await asyncio.sleep(0.1)

        started = collector.of_type("demo_started")
        assert started[0].team_name == "RehearsalTeam"

    @pytest.mark.asyncio
    async def test_total_event_count(self, event_bus: EventBus):
        """1 start + 3 frames + 3 transcripts + 1 stop = 8 events."""
        collector = EventCollector(event_bus)
        capture = SyntheticCapture(event_bus)

        await capture.run_demo()
        await asyncio.sleep(0.1)

        assert len(collector.events) == 8


class TestSyntheticTranscripts:
    def test_transcript_data_integrity(self):
        """The pre-defined transcripts have expected shape."""
        assert len(_SYNTHETIC_TRANSCRIPTS) == 3
        for seg in _SYNTHETIC_TRANSCRIPTS:
            assert seg.text
            assert seg.timestamp > 0
            assert seg.is_final is True
