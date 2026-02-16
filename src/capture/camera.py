"""Async camera frame capture with JPEG encoding and key frame detection.

Captures frames from an OpenCV VideoCapture device at ~1 FPS, converts to RGB,
thumbnails to a configurable max dimension, encodes as JPEG, and publishes
FrameCaptured events to the event bus. Key frames (significant visual changes)
also trigger KeyFrameDetected events.

All blocking OpenCV calls are wrapped with asyncio.to_thread() to avoid
blocking the event loop.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging

import cv2
import numpy as np
import PIL.Image

from src.capture.config import CaptureConfig
from src.capture.event_bus import EventBus
from src.capture.key_frames import KeyFrameDetector
from src.capture.models import FrameCaptured, FrameData, KeyFrameDetected, MediaChunk

logger = logging.getLogger(__name__)


class CameraCapture:
    """Async camera frame capture with JPEG encoding and key frame detection.

    Runs as an asyncio task. Opens the configured camera device, captures frames
    at the configured frame rate (~1 FPS default), and publishes events for each
    frame. Frames that differ significantly from the previous frame are flagged
    as key frames.

    Media chunks (JPEG data) are placed into the output queue for downstream
    consumption (e.g., Gemini session). Queue overflow is handled gracefully
    by dropping frames.
    """

    def __init__(
        self,
        config: CaptureConfig,
        event_bus: EventBus,
        out_queue: asyncio.Queue,
    ) -> None:
        """Initialize camera capture.

        Args:
            config: Capture configuration with device index, frame rate, etc.
            event_bus: Event bus for publishing FrameCaptured/KeyFrameDetected events.
            out_queue: Bounded queue for media chunks destined for Gemini.
        """
        self._config = config
        self._event_bus = event_bus
        self._out_queue = out_queue
        self._stop_event = asyncio.Event()
        self.key_frame_detector = KeyFrameDetector(threshold=config.key_frame_threshold)

    def _capture_and_encode(self, cap: cv2.VideoCapture) -> tuple[FrameData, np.ndarray] | None:
        """Capture a single frame, convert to JPEG with thumbnail. Synchronous.

        This method runs in a thread via asyncio.to_thread() to avoid blocking
        the event loop. Performs: cap.read() -> BGR-to-RGB -> PIL thumbnail ->
        JPEG encode -> base64 encode.

        Args:
            cap: An opened OpenCV VideoCapture device.

        Returns:
            A tuple of (FrameData, raw_numpy_frame) or None if read fails.
        """
        ret, frame = cap.read()
        if not ret:
            return None

        # Convert BGR -> RGB for PIL
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)

        # Thumbnail to max dimension (preserves aspect ratio)
        max_dim = self._config.frame_max_dimension
        img.thumbnail([max_dim, max_dim])

        # Encode as JPEG
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()

        # Base64 encode for Gemini API
        b64_data = base64.b64encode(jpeg_bytes).decode("utf-8")

        import time

        frame_data = FrameData(
            jpeg_data=jpeg_bytes,
            width=img.width,
            height=img.height,
            timestamp=time.time(),
            is_key_frame=False,
        )

        return (frame_data, frame)

    async def run(self) -> None:
        """Main capture loop. Opens camera and captures frames until stopped.

        Raises:
            RuntimeError: If the camera device cannot be opened.
        """
        self._stop_event.clear()

        logger.info(
            "Starting camera capture on device %d at %.1f FPS",
            self._config.camera_device_index,
            self._config.frame_rate,
        )

        cap = await asyncio.to_thread(cv2.VideoCapture, self._config.camera_device_index)

        if not cap.isOpened():
            logger.error(
                "Cannot open camera device %d. "
                "Check that the device is connected and not in use by another application.",
                self._config.camera_device_index,
            )
            return

        try:
            while not self._stop_event.is_set():
                result = await asyncio.to_thread(self._capture_and_encode, cap)
                if result is None:
                    logger.warning("Camera read failed, ending capture loop")
                    break

                frame_data, raw_frame = result

                # Check for key frame
                is_kf = self.key_frame_detector.check(raw_frame)
                frame_data.is_key_frame = is_kf

                # Publish FrameCaptured event
                self._event_bus.publish(FrameCaptured(frame=frame_data))

                # If key frame, also publish KeyFrameDetected
                if is_kf:
                    self._event_bus.publish(KeyFrameDetected(frame=frame_data))
                    logger.debug("Key frame detected and published")

                # Put media chunk into output queue for Gemini consumption
                chunk = MediaChunk(
                    mime_type="image/jpeg",
                    data=frame_data.jpeg_data,
                )
                try:
                    self._out_queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    logger.warning("Output queue full, dropping frame")

                # Sleep to maintain target frame rate
                await asyncio.sleep(1.0 / self._config.frame_rate)
        finally:
            await asyncio.to_thread(cap.release)
            logger.info("Camera capture stopped, device released")

    async def stop(self) -> None:
        """Signal the capture loop to stop and reset the key frame detector."""
        self._stop_event.set()
        self.key_frame_detector.reset()
        logger.info("Camera capture stop requested")
