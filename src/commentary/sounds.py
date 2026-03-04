"""Programmatic sound effect generation for production-quality event cues.

Generates short audio stingers (chimes, buzzes, alerts) as PCM int16 bytes
for playback through PyAudio. All sounds are synthesized with numpy — no
external audio files needed.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 44100


def _envelope(length: int, attack: int, release: int) -> np.ndarray:
    """Generate an ADSR-style amplitude envelope (attack + sustain + release)."""
    env = np.ones(length, dtype=np.float32)
    if attack > 0:
        env[:attack] = np.linspace(0, 1, attack, dtype=np.float32)
    if release > 0:
        env[-release:] = np.linspace(1, 0, release, dtype=np.float32)
    return env


def _to_pcm16(audio: np.ndarray) -> bytes:
    """Convert float32 audio [-1, 1] to PCM int16 bytes."""
    clipped = np.clip(audio, -0.95, 0.95)
    return (clipped * 32767).astype(np.int16).tobytes()


def generate_start_chime() -> bytes:
    """Rising two-tone chime for demo start (~400ms)."""
    sr = _SAMPLE_RATE
    # Two ascending notes: C5 (523Hz) → E5 (659Hz)
    t1 = np.arange(int(sr * 0.2), dtype=np.float32) / sr
    t2 = np.arange(int(sr * 0.2), dtype=np.float32) / sr

    note1 = np.sin(2 * np.pi * 523 * t1) * _envelope(len(t1), int(sr * 0.01), int(sr * 0.05))
    note2 = np.sin(2 * np.pi * 659 * t2) * _envelope(len(t2), int(sr * 0.01), int(sr * 0.08))

    audio = np.concatenate([note1, note2]) * 0.3
    return _to_pcm16(audio)


def generate_stop_tone() -> bytes:
    """Low descending tone for demo stop (~300ms)."""
    sr = _SAMPLE_RATE
    duration = int(sr * 0.3)

    # Descending sweep from 440Hz to 220Hz
    freq = np.linspace(440, 220, duration)
    audio = np.sin(2 * np.pi * np.cumsum(freq) / sr)
    audio *= _envelope(duration, int(sr * 0.01), int(sr * 0.1))
    audio *= 0.25

    return _to_pcm16(audio.astype(np.float32))


def generate_injection_alert() -> bytes:
    """Short warning "whoop" for injection detection (~350ms)."""
    sr = _SAMPLE_RATE
    duration = int(sr * 0.35)

    # Quick ascending sweep 300Hz → 800Hz
    freq = np.linspace(300, 800, duration)
    audio = np.sin(2 * np.pi * np.cumsum(freq) / sr)
    audio *= _envelope(duration, int(sr * 0.005), int(sr * 0.1))
    audio *= 0.2

    return _to_pcm16(audio.astype(np.float32))


class SoundEffects:
    """Pre-generated sound effects for venue production cues.

    All sounds are generated once at init and cached as PCM int16 bytes,
    ready for direct PyAudio stream.write() playback.
    """

    def __init__(self) -> None:
        self.start_chime = generate_start_chime()
        self.stop_tone = generate_stop_tone()
        self.injection_alert = generate_injection_alert()
        logger.debug("Sound effects generated (%d cues)", 3)
