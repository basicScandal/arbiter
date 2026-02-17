"""Real-time audio processing for TTS venue PA playback.

Applies EQ, compression, and limiting to PCM audio chunks to ensure
warm, full-bodied sound at consistent levels on the PA system.
"""

from __future__ import annotations

import math

import numpy as np


def _low_shelf_coeffs(gain_db: float, freq: float, sample_rate: float) -> tuple[np.ndarray, np.ndarray]:
    """Compute biquad coefficients for a low-shelf filter.

    Args:
        gain_db: Gain in dB (positive = boost, negative = cut).
        freq: Shelf corner frequency in Hz.
        sample_rate: Audio sample rate in Hz.

    Returns:
        Tuple of (b, a) coefficient arrays for the biquad filter.
    """
    A = 10 ** (gain_db / 40.0)  # amplitude factor (square root of linear gain)
    w0 = 2.0 * math.pi * freq / sample_rate
    alpha = math.sin(w0) / 2.0 * math.sqrt(2.0)  # Q = 0.707 (Butterworth)

    cos_w0 = math.cos(w0)
    two_sqrt_A_alpha = 2.0 * math.sqrt(A) * alpha

    b0 = A * ((A + 1) - (A - 1) * cos_w0 + two_sqrt_A_alpha)
    b1 = 2 * A * ((A - 1) - (A + 1) * cos_w0)
    b2 = A * ((A + 1) - (A - 1) * cos_w0 - two_sqrt_A_alpha)
    a0 = (A + 1) + (A - 1) * cos_w0 + two_sqrt_A_alpha
    a1 = -2 * ((A - 1) + (A + 1) * cos_w0)
    a2 = (A + 1) + (A - 1) * cos_w0 - two_sqrt_A_alpha

    b = np.array([b0 / a0, b1 / a0, b2 / a0], dtype=np.float32)
    a = np.array([1.0, a1 / a0, a2 / a0], dtype=np.float32)
    return b, a


def _high_shelf_coeffs(gain_db: float, freq: float, sample_rate: float) -> tuple[np.ndarray, np.ndarray]:
    """Compute biquad coefficients for a high-shelf filter.

    Args:
        gain_db: Gain in dB (positive = boost, negative = cut).
        freq: Shelf corner frequency in Hz.
        sample_rate: Audio sample rate in Hz.

    Returns:
        Tuple of (b, a) coefficient arrays for the biquad filter.
    """
    A = 10 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * freq / sample_rate
    alpha = math.sin(w0) / 2.0 * math.sqrt(2.0)

    cos_w0 = math.cos(w0)
    two_sqrt_A_alpha = 2.0 * math.sqrt(A) * alpha

    b0 = A * ((A + 1) + (A - 1) * cos_w0 + two_sqrt_A_alpha)
    b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
    b2 = A * ((A + 1) + (A - 1) * cos_w0 - two_sqrt_A_alpha)
    a0 = (A + 1) - (A - 1) * cos_w0 + two_sqrt_A_alpha
    a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
    a2 = (A + 1) - (A - 1) * cos_w0 - two_sqrt_A_alpha

    b = np.array([b0 / a0, b1 / a0, b2 / a0], dtype=np.float32)
    a = np.array([1.0, a1 / a0, a2 / a0], dtype=np.float32)
    return b, a


class AudioProcessor:
    """Real-time audio processor for PCM int16 TTS chunks.

    Processes raw PCM signed 16-bit little-endian audio with:
    - Low-shelf warmth boost (+3dB below 300Hz)
    - High-shelf de-harsh cut (-2dB above 8kHz)
    - Gentle compression (threshold -12dB, ratio 2:1, with makeup gain)
    - Hard limiter (ceiling -1dB)

    Maintains filter state between chunks for seamless streaming.
    Designed for <10ms processing latency on typical chunk sizes.
    """

    def __init__(self, enabled: bool = True, sample_rate: int = 44100) -> None:
        """Initialize audio processor.

        Args:
            enabled: Whether processing is active. If False, chunks pass through unmodified.
            sample_rate: Audio sample rate in Hz (must match TTS output).
        """
        self.enabled = enabled

        # Compression: gentle settings that preserve natural speech dynamics
        self._comp_threshold = 0.251  # -12dB in linear scale (10^(-12/20))
        self._comp_ratio = 2.0
        self._makeup_gain = 1.25  # ~+2dB to restore volume after compression

        # Limiter
        self._limiter_ceiling = 0.891  # -1dB in linear scale (10^(-1/20))

        # EQ: biquad shelf filters for warmth and de-harshness
        self._warmth_b, self._warmth_a = _low_shelf_coeffs(
            gain_db=3.0, freq=300.0, sample_rate=sample_rate,
        )
        self._deharsh_b, self._deharsh_a = _high_shelf_coeffs(
            gain_db=-2.0, freq=8000.0, sample_rate=sample_rate,
        )

        # Filter state (maintained across chunks for seamless streaming)
        self._warmth_state = np.zeros(2, dtype=np.float32)
        self._deharsh_state = np.zeros(2, dtype=np.float32)

    def process_chunk(self, audio_bytes: bytes) -> bytes:
        """Process a PCM int16 audio chunk with EQ, compression, and limiting.

        Args:
            audio_bytes: Raw PCM signed 16-bit little-endian audio bytes.

        Returns:
            Processed PCM int16 bytes with same length as input.
        """
        if not self.enabled:
            return audio_bytes

        audio = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float = audio.astype(np.float32) / 32768.0

        # EQ: warmth boost + de-harshness
        audio_float = self._apply_biquad(audio_float, self._warmth_b, self._warmth_a, self._warmth_state)
        audio_float = self._apply_biquad(audio_float, self._deharsh_b, self._deharsh_a, self._deharsh_state)

        # Dynamics: compress then limit
        audio_float = self._compress(audio_float)
        audio_float = self._limit(audio_float)

        audio_int16 = (audio_float * 32767.0).astype(np.int16)
        return audio_int16.tobytes()

    def _apply_biquad(
        self,
        audio: np.ndarray,
        b: np.ndarray,
        a: np.ndarray,
        state: np.ndarray,
    ) -> np.ndarray:
        """Apply a biquad filter with persistent state across chunks.

        Uses Direct Form II transposed for numerical stability.

        Args:
            audio: Float32 audio samples.
            b: Numerator (feedforward) coefficients [b0, b1, b2].
            a: Denominator (feedback) coefficients [1, a1, a2].
            state: 2-element delay line, mutated in place.

        Returns:
            Filtered audio samples.
        """
        out = np.empty_like(audio)
        s0, s1 = state[0], state[1]

        for i in range(len(audio)):
            x = audio[i]
            y = b[0] * x + s0
            s0 = b[1] * x - a[1] * y + s1
            s1 = b[2] * x - a[2] * y
            out[i] = y

        state[0], state[1] = s0, s1
        return out

    def _compress(self, audio: np.ndarray) -> np.ndarray:
        """Apply dynamic range compression with makeup gain.

        Args:
            audio: Float32 audio samples in range [-1.0, 1.0].

        Returns:
            Compressed audio samples with makeup gain applied.
        """
        abs_audio = np.abs(audio)

        gain = np.ones_like(abs_audio)
        above_threshold = abs_audio > self._comp_threshold

        if np.any(above_threshold):
            compressed_level = (
                self._comp_threshold +
                (abs_audio[above_threshold] - self._comp_threshold) / self._comp_ratio
            )
            gain[above_threshold] = compressed_level / abs_audio[above_threshold]

        return audio * gain * self._makeup_gain

    def _limit(self, audio: np.ndarray) -> np.ndarray:
        """Apply hard limiting to prevent clipping.

        Args:
            audio: Float32 audio samples.

        Returns:
            Limited audio samples, clipped to ceiling.
        """
        return np.clip(audio, -self._limiter_ceiling, self._limiter_ceiling)
