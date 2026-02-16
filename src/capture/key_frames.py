"""Key frame detection via histogram comparison.

Compares consecutive frame histograms to detect significant visual changes
(slide transitions, switching from slides to terminal, etc.). Uses OpenCV's
cv2.compareHist with correlation metric -- low correlation means a scene change.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class KeyFrameDetector:
    """Detects significant visual changes between consecutive frames.

    Uses grayscale histogram comparison with cv2.HISTCMP_CORREL.
    Correlation of 1.0 means identical frames; values below the threshold
    indicate a key frame (scene change).

    The first frame checked is always treated as a key frame.
    """

    def __init__(self, threshold: float = 0.4) -> None:
        """Initialize the key frame detector.

        Args:
            threshold: Correlation threshold below which a frame is considered
                a key frame. Lower values mean more sensitivity (fewer key frames).
                Default 0.4 catches major scene changes like slide transitions.
        """
        self._threshold = threshold
        self._prev_hist: np.ndarray | None = None

    def check(self, frame: np.ndarray) -> bool:
        """Check whether a frame is a key frame (significant visual change).

        Args:
            frame: A BGR or RGB numpy array (OpenCV frame format).

        Returns:
            True if this frame is a key frame (first frame, or correlation
            with previous frame is below the threshold).
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        cv2.normalize(hist, hist)

        if self._prev_hist is None:
            self._prev_hist = hist
            logger.debug("First frame is always a key frame")
            return True

        correlation = cv2.compareHist(self._prev_hist, hist, cv2.HISTCMP_CORREL)
        self._prev_hist = hist

        is_key = correlation < self._threshold
        if is_key:
            logger.debug("Key frame detected (correlation=%.3f < threshold=%.3f)", correlation, self._threshold)
        return is_key

    def reset(self) -> None:
        """Clear previous histogram state (call between demos)."""
        self._prev_hist = None
        logger.debug("Key frame detector reset")
