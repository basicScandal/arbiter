"""Event-driven defense pipeline orchestrator.

Wires OCR scanning, injection detection, sanitization, roast generation, and
injection logging into a cohesive pipeline that subscribes to capture events
via the shared event bus. Key frames are OCR-scanned for visual injection,
transcripts are scanned for verbal injection, and on demo stop all Gemini
observations are sanitized before being published for downstream consumers.

Roast generation fires as a detached asyncio task -- it never blocks the
pipeline. Only HIGH confidence detections trigger roast generation; all
detections are logged regardless of confidence.
"""

from __future__ import annotations

import asyncio
import logging
import re

from src.capture.event_bus import EventBus
from src.capture.gemini_session import GeminiSession
from src.capture.models import (
    DemoStarted,
    DemoStopped,
    KeyFrameDetected,
    TranscriptReceived,
)
from src.defense.injection_detector import InjectionDetector
from src.defense.injection_logger import InjectionLogger
from src.defense.models import (
    InjectionAttempt,
    InjectionDetected,
    ObservationVerified,
    RoastGenerated,
)
from src.defense.ocr_scanner import OCRScanner
from src.defense.roast_generator import RoastGenerator
from src.defense.sanitizer import ObservationSanitizer

logger = logging.getLogger(__name__)

# Sentence-ending punctuation for splitting reassembled token streams
_SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+')


def _reassemble_tokens(tokens: list[str]) -> list[str]:
    """Join token-level fragments into sentence-level strings for scanning.

    Gemini Live API streams observations/transcripts as individual tokens
    (e.g., [" ignore", " all", " previous", " instructions"]). Injection
    detection regexes require multi-word phrases in a single string.
    This function concatenates tokens and splits on sentence boundaries.

    Args:
        tokens: List of token-level text fragments.

    Returns:
        List of sentence-level strings suitable for regex scanning.
    """
    if not tokens:
        return []

    full_text = "".join(tokens).strip()
    if not full_text:
        return []

    # Split on sentence-ending punctuation
    sentences = _SENTENCE_ENDINGS.split(full_text)
    return [s.strip() for s in sentences if s.strip()]


class DefensePipeline:
    """Orchestrates all defense components via event bus subscriptions.

    Subscribes to capture events (key_frame_detected, transcript_received,
    demo_started, demo_stopped) and processes them through the defense chain:
    OCR extraction, injection detection, roast generation, logging, and
    observation sanitization.

    Args:
        api_key: Gemini API key for roast generation.
        gemini_session: Optional GeminiSession reference for accessing
            raw observations on demo stop.
    """

    def __init__(
        self,
        api_key: str,
        gemini_session: GeminiSession | None = None,
    ) -> None:
        self._ocr = OCRScanner()
        self._detector = InjectionDetector()
        self._sanitizer = ObservationSanitizer(self._detector)
        self._roaster = RoastGenerator(api_key=api_key)
        self._logger = InjectionLogger()
        self._gemini = gemini_session

        self._event_bus: EventBus | None = None
        self._current_team: str = ""
        self._roasts: list[str] = []
        self._transcripts: list[str] = []
        self._transcript_buffer: str = ""
        self._transcript_cooldown: int = 0
        self._logged_medium_in_window: bool = False
        self._pending_roast_tasks: list[asyncio.Task] = []
        self._ocr_texts: list[str] = []

    async def setup(self, event_bus: EventBus) -> None:
        """Subscribe to capture events on the shared event bus.

        Args:
            event_bus: The shared event bus from the capture pipeline.
        """
        self._event_bus = event_bus
        event_bus.subscribe("key_frame_detected", self._on_key_frame)
        event_bus.subscribe("transcript_received", self._on_transcript)
        event_bus.subscribe("demo_started", self._on_demo_started)
        event_bus.subscribe("demo_stopped", self._on_demo_stopped)
        logger.info("Defense pipeline armed")

    async def _on_demo_started(self, event: DemoStarted) -> None:
        """Reset state for a fresh demo session."""
        self._current_team = event.team_name
        self._roasts.clear()
        self._transcripts.clear()
        self._transcript_buffer = ""
        self._transcript_cooldown = 0
        self._logged_medium_in_window = False
        self._ocr_texts.clear()
        for task in self._pending_roast_tasks:
            if not task.done():
                task.cancel()
        self._pending_roast_tasks.clear()
        self._logger.clear()
        logger.info("Defense pipeline active for team: %s", event.team_name)

    async def _on_key_frame(self, event: KeyFrameDetected) -> None:
        """OCR-scan a key frame and check for visual injection patterns."""
        ocr_text = await asyncio.to_thread(
            self._ocr.extract_text, event.frame.jpeg_data
        )
        if not ocr_text:
            return

        # Accumulate OCR text for cross-reference validation at demo stop
        self._ocr_texts.append(ocr_text)

        result = self._detector.scan_visual(ocr_text)
        if result.is_injection:
            attempt = InjectionAttempt(
                timestamp=event.timestamp,
                injection_type="visual",
                content=result.matched_text,
                pattern=",".join(result.matched_patterns),
                confidence=result.confidence,
                team_name=self._current_team,
            )
            self._logger.log(attempt)
            if self._event_bus is not None:
                self._event_bus.publish(InjectionDetected(attempt=attempt))
            if result.confidence == "high":
                task = asyncio.create_task(self._generate_roast(attempt), name="roast-visual")
                self._pending_roast_tasks.append(task)

    async def _on_transcript(self, event: TranscriptReceived) -> None:
        """Scan transcript text for verbal injection patterns.

        Gemini Live API streams transcripts token-by-token (e.g., " ig",
        "nore", " all"). Individual tokens never match multi-word injection
        patterns. We accumulate tokens into a sliding buffer and scan the
        trailing window so patterns spanning multiple tokens are detected.

        Cooldown only triggers after HIGH confidence detections (which fire
        roast generation). Medium detections are logged but scanning continues
        so additional patterns can accumulate to reach high confidence.
        """
        self._transcripts.append(event.segment.text)
        self._transcript_buffer = (self._transcript_buffer + event.segment.text)[-400:]

        # Skip scanning during cooldown after a high-confidence detection
        if self._transcript_cooldown > 0:
            self._transcript_cooldown -= 1
            return

        # Scan the trailing window (last 200 chars covers any injection phrase)
        window = self._transcript_buffer[-200:]
        result = self._detector.scan_verbal(window)
        if result.is_injection:
            # Only log and fire events on confidence upgrade (avoid duplicates
            # at the same confidence level from overlapping windows)
            if result.confidence == "high":
                attempt = InjectionAttempt(
                    timestamp=event.timestamp,
                    injection_type="verbal",
                    content=result.matched_text or window.strip()[:200],
                    pattern=",".join(result.matched_patterns),
                    confidence=result.confidence,
                    team_name=self._current_team,
                )
                # Cooldown after high confidence — we got the roast-worthy detection.
                # Only 5 events: enough to avoid immediate duplicate roasts while
                # keeping scanning responsive. This cooldown only affects real-time
                # roasting; sanitization at demo stop always rescans all transcripts.
                self._transcript_cooldown = 5
                # Reset medium flag so new medium detections after cooldown are logged
                self._logged_medium_in_window = False
                self._logger.log(attempt)
                if self._event_bus is not None:
                    self._event_bus.publish(InjectionDetected(attempt=attempt))
                task = asyncio.create_task(self._generate_roast(attempt), name="roast-verbal")
                self._pending_roast_tasks.append(task)
            elif not self._logged_medium_in_window:
                # Log first medium detection but keep scanning for more patterns
                attempt = InjectionAttempt(
                    timestamp=event.timestamp,
                    injection_type="verbal",
                    content=result.matched_text or window.strip()[:200],
                    pattern=",".join(result.matched_patterns),
                    confidence=result.confidence,
                    team_name=self._current_team,
                )
                self._logged_medium_in_window = True
                self._logger.log(attempt)
                if self._event_bus is not None:
                    self._event_bus.publish(InjectionDetected(attempt=attempt))

    async def _generate_roast(self, attempt: InjectionAttempt) -> None:
        """Generate a roast for a high-confidence injection attempt."""
        roast = await self._roaster.generate(attempt)
        # Guard: discard roast if the demo has moved to a different team
        if attempt.team_name != self._current_team:
            logger.debug(
                "Discarding stale roast for team %s (current team: %s)",
                attempt.team_name, self._current_team,
            )
            return
        self._roasts.append(roast)
        if self._event_bus is not None:
            self._event_bus.publish(
                RoastGenerated(roast=roast, attempt=attempt)
            )
        logger.info("ROAST: %s", roast)

    async def _on_demo_stopped(self, event: DemoStopped) -> None:
        """Sanitize observations and publish verified output on demo stop."""
        try:
            await self._process_demo_stopped(event)
        except Exception:
            logger.exception(
                "CRITICAL: _on_demo_stopped failed for team '%s' — "
                "ObservationVerified may not have been published, "
                "downstream scoring/commentary will be skipped",
                event.team_name,
            )

    async def _process_demo_stopped(self, event: DemoStopped) -> None:
        """Inner implementation of demo-stop processing."""
        # Wait for any pending roast tasks to complete (short timeout)
        if self._pending_roast_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        *self._pending_roast_tasks, return_exceptions=True
                    ),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Timed out waiting for %d pending roast tasks",
                    len(self._pending_roast_tasks),
                )
                # Cancel orphaned tasks to prevent cross-demo corruption
                for task in self._pending_roast_tasks:
                    if not task.done():
                        task.cancel()
            self._pending_roast_tasks.clear()

        # Get raw observations from the Gemini session
        raw_observations: list[str] = []
        if self._gemini is not None:
            raw_observations = self._gemini.get_observations()

        # Reassemble token-level observations into sentences for scanning.
        # Gemini Live API streams observations token-by-token (e.g., " ignore",
        # " all", " previous"), so individual tokens miss multi-word patterns.
        reassembled = _reassemble_tokens(raw_observations)

        # Scan reassembled observations for injection residue and log any found
        for obs in reassembled:
            result = self._detector.scan_observation(obs)
            if result.is_injection:
                attempt = InjectionAttempt(
                    timestamp=event.timestamp,
                    injection_type="observation",
                    content=result.matched_text,
                    pattern=",".join(result.matched_patterns),
                    confidence=result.confidence,
                    team_name=self._current_team,
                )
                self._logger.log(attempt)

        # Cross-reference each observation against accumulated OCR slide texts.
        # If an observation closely mirrors slide text (>60% word overlap), it
        # may be "observation laundering" — Gemini parroting evaluative text
        # from a slide rather than describing actual code behaviour.
        if self._ocr_texts:
            for obs in reassembled:
                is_suspicious, detail = self._detector.cross_reference_observation(
                    obs, self._ocr_texts
                )
                if is_suspicious:
                    attempt = InjectionAttempt(
                        timestamp=event.timestamp,
                        injection_type="observation",
                        content=obs[:200],
                        pattern="cross_reference",
                        confidence="medium",
                        team_name=self._current_team,
                    )
                    self._logger.log(attempt)
                    logger.info(
                        "Cross-reference flag [%s]: %s",
                        self._current_team,
                        detail,
                    )
                    if self._event_bus is not None:
                        self._event_bus.publish(
                            InjectionDetected(attempt=attempt)
                        )

        # Reassemble transcripts from token fragments for sanitization
        reassembled_transcripts = _reassemble_tokens(self._transcripts)

        # Create sanitized output bundle using reassembled text
        sanitized = self._sanitizer.create_sanitized_output(
            team_name=event.team_name,
            observations=reassembled,
            transcripts=reassembled_transcripts,
            attempts=self._logger.get_attempts(),
            duration=event.duration,
            roasts=list(self._roasts),
        )

        # Publish for downstream consumers (Phase 3/4)
        if self._event_bus is not None:
            self._event_bus.publish(ObservationVerified(output=sanitized))

        attempts = self._logger.get_attempts()
        logger.info(
            "Defense summary: %d injection attempts, %d observations sanitized, %d roasts generated",
            len(attempts),
            len(sanitized.observations),
            len(self._roasts),
        )
