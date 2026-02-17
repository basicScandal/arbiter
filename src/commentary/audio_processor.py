"""Real-time audio processing for TTS venue PA playback.

Applies compression and limiting to PCM audio chunks to ensure
consistent levels and prevent clipping on the PA system.
"""

from __future__ import annotations

import numpy as np


class AudioProcessor:
    """Real-time audio processor for PCM int16 TTS chunks.

    Processes raw PCM signed 16-bit little-endian audio with:
    - Light compression (threshold -20dB, ratio 3:1)
    - Hard limiter (ceiling -1dB)

    Designed for <10ms processing latency on typical chunk sizes.
    """

    def __init__(self, enabled: bool = True) -> None:
        """Initialize audio processor.

        Args:
            enabled: Whether processing is active. If False, chunks pass through unmodified.
        """
        self.enabled = enabled

        # Compression parameters
        self._comp_threshold = 0.1  # -20dB in linear scale (10^(-20/20))
        self._comp_ratio = 3.0

        # Limiter parameters
        self._limiter_ceiling = 0.891  # -1dB in linear scale (10^(-1/20))

    def process_chunk(self, audio_bytes: bytes) -> bytes:
        """Process a PCM int16 audio chunk with compression and limiting.

        Args:
            audio_bytes: Raw PCM signed 16-bit little-endian audio bytes.

        Returns:
            Processed PCM int16 bytes with same length as input.
        """
        if not self.enabled:
            return audio_bytes

        # Convert bytes to int16 numpy array
        audio = np.frombuffer(audio_bytes, dtype=np.int16)

        # Convert to float32 in range [-1.0, 1.0]
        audio_float = audio.astype(np.float32) / 32768.0

        # Apply compression
        audio_float = self._compress(audio_float)

        # Apply hard limiter
        audio_float = self._limit(audio_float)

        # Convert back to int16
        audio_int16 = (audio_float * 32767.0).astype(np.int16)

        return audio_int16.tobytes()

    def _compress(self, audio: np.ndarray) -> np.ndarray:
        """Apply dynamic range compression.

        Args:
            audio: Float32 audio samples in range [-1.0, 1.0].

        Returns:
            Compressed audio samples.
        """
        # Get absolute values for level detection
        abs_audio = np.abs(audio)

        # Calculate gain reduction
        # Above threshold: compress by ratio, below: unity gain
        gain = np.ones_like(abs_audio)
        above_threshold = abs_audio > self._comp_threshold

        if np.any(above_threshold):
            # Gain reduction formula: threshold + (input - threshold) / ratio
            compressed_level = (
                self._comp_threshold +
                (abs_audio[above_threshold] - self._comp_threshold) / self._comp_ratio
            )
            gain[above_threshold] = compressed_level / abs_audio[above_threshold]

        return audio * gain

    def _limit(self, audio: np.ndarray) -> np.ndarray:
        """Apply hard limiting to prevent clipping.

        Args:
            audio: Float32 audio samples in range [-1.0, 1.0].

        Returns:
            Limited audio samples, clipped to ceiling.
        """
        return np.clip(audio, -self._limiter_ceiling, self._limiter_ceiling)
