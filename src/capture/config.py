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
    gemini_model: str = "gemini-2.5-flash-native-audio-preview-12-2025"
    max_queue_size: int = 5
    frame_max_dimension: int = 1024
    audio_sample_rate: int = 16000
    audio_channels: int = 1
    audio_chunk_size: int = 512
    compression_trigger_tokens: int = 25600
    compression_target_tokens: int = 12800
    cartesia_api_key: str = ""
    cartesia_voice_id: str = ""
    display_host: str = "0.0.0.0"
    display_port: int = 8080
    # MoE multi-model scoring and commentary enrichment
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""
    moe_scoring_enabled: bool = False
    commentary_enrichment_enabled: bool = False
    # Shared secret for operator WebSocket authentication.
    # When set, clients must pass ?token=<value> on the WS upgrade URL.
    # When empty, all connections are allowed (dev mode).
    operator_token: str = ""


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
        cartesia_api_key=os.getenv("CARTESIA_API_KEY", ""),
        cartesia_voice_id=os.getenv("CARTESIA_VOICE_ID", ""),
        display_host=os.getenv("DISPLAY_HOST", "0.0.0.0"),
        display_port=int(os.getenv("DISPLAY_PORT", "8080")),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        moe_scoring_enabled=os.getenv("MOE_SCORING_ENABLED", "").lower() in ("true", "1", "yes"),
        commentary_enrichment_enabled=os.getenv("COMMENTARY_ENRICHMENT_ENABLED", "").lower() in ("true", "1", "yes"),
        operator_token=os.getenv("OPERATOR_TOKEN", ""),
    )
