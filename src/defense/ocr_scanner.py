"""OCR text extraction from key frame images.

Uses pytesseract (Tesseract OCR engine) with grayscale + adaptive threshold
preprocessing optimized for camera-captured projected slides.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np
import pytesseract

logger = logging.getLogger(__name__)


class OCRScanner:
    """Extracts readable text from JPEG-encoded key frame images.

    Handles missing Tesseract gracefully -- logs a warning and returns
    empty strings instead of crashing. OCR is a defense layer, not a
    critical path.
    """

    def __init__(self) -> None:
        self._available = False
        try:
            version = pytesseract.get_tesseract_version()
            self._available = True
            logger.info("Tesseract OCR available: version %s", version)
        except pytesseract.TesseractNotFoundError:
            logger.warning(
                "Tesseract OCR not found. OCR scanning will be disabled. "
                "Install via: brew install tesseract (macOS) or apt install tesseract-ocr (Linux)"
            )

    @property
    def available(self) -> bool:
        """Whether the Tesseract OCR engine is available."""
        return self._available

    def extract_text(self, jpeg_data: bytes, timeout: int = 5) -> str:
        """Extract text from JPEG-encoded image data.

        Synchronous method -- call via asyncio.to_thread for non-blocking use.

        Args:
            jpeg_data: Raw JPEG bytes from a key frame capture.
            timeout: Maximum seconds for Tesseract OCR processing.

        Returns:
            Extracted text stripped of whitespace, or empty string on failure.
        """
        if not self._available:
            return ""

        if not jpeg_data:
            return ""

        # Decode JPEG bytes to numpy array
        nparr = np.frombuffer(jpeg_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            logger.warning("Failed to decode JPEG data for OCR")
            return ""

        # Preprocess: grayscale + adaptive threshold for projected slides
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        # Extract text with timeout protection
        try:
            text = pytesseract.image_to_string(
                thresh,
                config="--psm 3",  # Fully automatic page segmentation
                timeout=timeout,
            )
            return text.strip()
        except RuntimeError:
            logger.warning("Tesseract OCR timed out after %ds", timeout)
            return ""
