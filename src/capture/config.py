"""Configuration loading for the capture layer with environment variable support."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel


class CaptureConfig(BaseModel):
    """Configuration for the Arbiter capture layer.

    All settings have sensible defaults except gemini_api_key,
    which must be provided via environment or explicit parameter.
    """

    gemini_api_key: str
    camera_device_index: int = 0
    audio_device_index: int | None = None
    frame_rate: float = 1.0
    key_frame_threshold: float = 0.4
    gemini_model: str = "gemini-live-2.5-flash-preview"
    max_queue_size: int = 5
    frame_max_dimension: int = 1024
    audio_sample_rate: int = 16000
    audio_channels: int = 1
    audio_chunk_size: int = 512
    compression_trigger_tokens: int = 25600
    compression_target_tokens: int = 12800


def load_config() -> CaptureConfig:
    """Load capture configuration from environment variables.

    Reads from .env file if present, then overrides with environment variables.
    Raises ValueError if GEMINI_API_KEY is not set.
    """
    load_dotenv()

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable is required. "
            "Get your API key from https://aistudio.google.com/apikey "
            "and set it in .env or as an environment variable."
        )

    audio_device_raw = os.getenv("AUDIO_DEVICE_INDEX")
    audio_device_index = int(audio_device_raw) if audio_device_raw else None

    return CaptureConfig(
        gemini_api_key=gemini_api_key,
        camera_device_index=int(os.getenv("CAMERA_DEVICE_INDEX", "0")),
        audio_device_index=audio_device_index,
        frame_rate=float(os.getenv("FRAME_RATE", "1.0")),
        key_frame_threshold=float(os.getenv("KEY_FRAME_THRESHOLD", "0.4")),
    )
