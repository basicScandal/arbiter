"""Pre-flight hardware and service checks before demo start.

Validates camera, audio, and Gemini API availability before the operator
starts a demo. Returns actionable error messages so the operator knows
exactly what to fix. If checks fail, the demo state machine is NOT
transitioned -- the system stays in idle and can retry after fixes.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import cv2
import pyaudio

from src.capture.config import CaptureConfig

logger = logging.getLogger(__name__)


@dataclass
class PreflightResult:
    """Result of pre-flight checks."""

    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.ok = False
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    @property
    def summary(self) -> str:
        if self.ok and not self.warnings:
            return "All pre-flight checks passed"
        parts = []
        for err in self.errors:
            parts.append(f"FAIL: {err}")
        for warn in self.warnings:
            parts.append(f"WARN: {warn}")
        return "; ".join(parts)


def _check_camera(config: CaptureConfig) -> tuple[bool, str]:
    """Synchronous camera check. Opens device, reads one frame, releases."""
    cap = cv2.VideoCapture(config.camera_device_index)
    if not cap.isOpened():
        return False, f"Cannot open camera device {config.camera_device_index}"
    try:
        ret, frame = cap.read()
        if not ret or frame is None:
            return False, f"Camera device {config.camera_device_index} opened but returned no frames"
        return True, f"Camera OK ({frame.shape[1]}x{frame.shape[0]})"
    finally:
        cap.release()


def _check_audio(config: CaptureConfig) -> tuple[bool, str]:
    """Synchronous audio check. Opens stream briefly and closes."""
    pya = pyaudio.PyAudio()
    try:
        stream = pya.open(
            format=pyaudio.paInt16,
            channels=config.audio_channels,
            rate=config.audio_sample_rate,
            input=True,
            input_device_index=config.audio_device_index,
            frames_per_buffer=config.audio_chunk_size,
        )
        # Read one chunk to verify the stream actually works
        data = stream.read(config.audio_chunk_size, exception_on_overflow=False)
        stream.stop_stream()
        stream.close()
        if not data:
            return False, "Audio stream opened but returned no data"
        device_name = "default"
        if config.audio_device_index is not None:
            info = pya.get_device_info_by_index(config.audio_device_index)
            device_name = info.get("name", str(config.audio_device_index))
        return True, f"Audio OK ({device_name})"
    except Exception as e:
        return False, f"Audio device error: {e}"
    finally:
        pya.terminate()


async def run_preflight(config: CaptureConfig) -> PreflightResult:
    """Run all pre-flight checks before demo start.

    Camera and audio checks run in threads to avoid blocking the event loop.
    Returns a PreflightResult with pass/fail status and actionable messages.
    """
    result = PreflightResult()

    # Camera check (in thread — OpenCV blocks)
    try:
        cam_ok, cam_msg = await asyncio.to_thread(_check_camera, config)
        if cam_ok:
            logger.info("Pre-flight camera: %s", cam_msg)
        else:
            result.fail(cam_msg)
            logger.error("Pre-flight camera: %s", cam_msg)
    except Exception as e:
        result.fail(f"Camera check crashed: {e}")
        logger.exception("Pre-flight camera check exception")

    # Audio check (in thread — PyAudio blocks)
    try:
        audio_ok, audio_msg = await asyncio.to_thread(_check_audio, config)
        if audio_ok:
            logger.info("Pre-flight audio: %s", audio_msg)
        else:
            result.warn(audio_msg)
            logger.warning("Pre-flight audio: %s", audio_msg)
    except Exception as e:
        result.warn(f"Audio check crashed: {e}")
        logger.exception("Pre-flight audio check exception")

    # Gemini API key check (fast, no network call)
    if not config.gemini_api_key:
        result.fail("GEMINI_API_KEY not set")
    else:
        logger.info("Pre-flight Gemini API key: present")

    logger.info("Pre-flight result: %s", result.summary)
    return result
