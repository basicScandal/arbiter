"""Pydantic data models for capture events, demo metadata, and media chunks."""

from __future__ import annotations

import time

from pydantic import BaseModel, ConfigDict


class MediaChunk(BaseModel):
    """A chunk of media data (audio or video) for streaming to Gemini."""

    mime_type: str
    data: bytes
    timestamp: float = 0.0

    def __init__(self, **data):
        if "timestamp" not in data:
            data["timestamp"] = time.time()
        super().__init__(**data)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class FrameData(BaseModel):
    """A single captured camera frame with metadata."""

    raw_frame: bytes = b""
    jpeg_data: bytes
    width: int
    height: int
    timestamp: float
    is_key_frame: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True, json_schema_extra={"exclude": {"raw_frame"}})


class TranscriptSegment(BaseModel):
    """A segment of transcribed presenter speech."""

    text: str
    timestamp: float
    is_final: bool = False


class DemoSession(BaseModel):
    """Tracks a single team's demo session with captured data."""

    team_name: str
    started_at: float | None = None
    stopped_at: float | None = None
    key_frames: list[FrameData] = []
    transcripts: list[TranscriptSegment] = []


class CaptureEvent(BaseModel):
    """Base event model for the capture event bus."""

    event_type: str
    timestamp: float = 0.0
    payload: dict = {}

    def __init__(self, **data):
        if "timestamp" not in data:
            data["timestamp"] = time.time()
        super().__init__(**data)


class DemoStarted(CaptureEvent):
    """Emitted when a demo capture session begins."""

    event_type: str = "demo_started"
    team_name: str


class DemoStopped(CaptureEvent):
    """Emitted when a demo capture session ends."""

    event_type: str = "demo_stopped"
    team_name: str
    duration: float = 0.0


class FrameCaptured(CaptureEvent):
    """Emitted when a new camera frame is captured."""

    event_type: str = "frame_captured"
    frame: FrameData

    model_config = ConfigDict(arbitrary_types_allowed=True)


class KeyFrameDetected(CaptureEvent):
    """Emitted when a key frame (significant visual change) is detected."""

    event_type: str = "key_frame_detected"
    frame: FrameData

    model_config = ConfigDict(arbitrary_types_allowed=True)


class DemoPaused(CaptureEvent):
    """Emitted when the operator pauses a running demo."""

    event_type: str = "demo_paused"
    team_name: str


class DemoResumed(CaptureEvent):
    """Emitted when the operator resumes a paused demo."""

    event_type: str = "demo_resumed"
    team_name: str


class TranscriptReceived(CaptureEvent):
    """Emitted when a new transcript segment is available."""

    event_type: str = "transcript_received"
    segment: TranscriptSegment
