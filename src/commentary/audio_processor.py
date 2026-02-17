"""Real-time audio processing for TTS venue PA playback.

Applies soft limiting to PCM audio chunks to prevent clipping
without coloring the natural Cartesia TTS output.
"""

from __future__ import annotations

import numpy as np


class AudioProcessor:
    """Real-time audio processor for PCM int16 TTS chunks.

    Applies only a soft limiter (ceiling -0.4dB) to prevent clipping.
    No EQ or compression — lets the Cartesia voice come through clean.
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._limiter_ceiling = 0.95  # -0.4dB, gentle safety net

    def process_chunk(self, audio_bytes: bytes) -> bytes:
        """Process a PCM int16 audio chunk with soft limiting only."""
        if not self.enabled:
            return audio_bytes

        audio = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float = audio.astype(np.float32) / 32768.0

        # Just limit to prevent clipping — no EQ, no compression
        audio_float = np.clip(audio_float, -self._limiter_ceiling, self._limiter_ceiling)

        audio_int16 = (audio_float * 32767.0).astype(np.int16)
        return audio_int16.tobytes()
