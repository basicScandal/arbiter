"""Commentary pipeline orchestrator wiring generator, TTS, display, and Q&A.

Subscribes to observation_verified and qa_requested events on the shared
event bus. When a demo stops and observations are verified, generates
streaming commentary, speaks it via TTS, and displays it on screen
simultaneously. When the operator triggers Q&A, generates and delivers
pointed questions.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
import uuid

from src.capture.event_bus import EventBus
from src.capture.models import DemoStarted, DemoStopped
from src.commentary.display_server import DisplayServer
from src.commentary.generator import CommentaryGenerator
from src.commentary.models import CommentaryDelivered, QARequested
from src.commentary.qa_generator import QAGenerator
from src.commentary.sounds import SoundEffects
from src.commentary.tts_engine import TTSEngine
from src.defense.models import InjectionDetected, ObservationVerified, SanitizedOutput
from src.resilience.circuit_breaker import GeminiCircuitBreaker
from src.resilience.health import default_health
from src.resilience.metrics import default_metrics

logger = logging.getLogger(__name__)

# Max seconds to wait for streaming commentary before giving up.
# Partial sentences delivered before timeout are still kept.
# Includes TTS playback time (~7s per sentence), so 90s allows ~10 sentences.
_COMMENTARY_TIMEOUT = 90

# Outer safety net wrapping the entire commentary handler.
# Catches edge cases the inner _COMMENTARY_TIMEOUT misses (e.g.
# _deliver_sentence hangs on display push, generator close() blocks).
# Must be > _COMMENTARY_TIMEOUT to let the inner timeout fire first
# under normal conditions.
_PIPELINE_TIMEOUT = 120

# Pre-written injection quips for zero-latency real-time reactions.
# {type} is replaced with the injection type (e.g. "prompt_injection").
_INJECTION_QUIPS: list[str] = [
    "Oh, someone's trying to hack the judge. How original.",
    "Nice try. Injection detected. Arbiter sees all.",
    "Did someone really just try that? Points for audacity, zero for subtlety.",
    "Prompt injection attempt detected. I'm flattered, really.",
    "Cute. Someone thought they could slip one past me.",
    "I've seen better injection attempts from a first-year CS student.",
    "Security hackathon, and you're trying to hack the judge? Bold.",
    "That injection attempt was almost as subtle as a fire alarm.",
    "Someone just tried to compromise the judge. The audacity is noted.",
    "Injection blocked. You'll have to impress me the old-fashioned way.",
]


class CommentaryPipeline:
    """Orchestrates commentary generation, TTS, and display delivery.

    Subscribes to event bus for automatic post-demo commentary and
    operator-triggered Q&A. Streams sentences to TTS and display in
    parallel for each sentence, ensuring no dead silence between
    generation and delivery.

    Args:
        api_key: Gemini API key for commentary and Q&A generation.
        voice_id: Cartesia voice ID for TTS.
        display_host: Display server bind address.
        display_port: Display server port.
    """

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        display_host: str = "0.0.0.0",
        display_port: int = 8080,
        groq_api_key: str = "",
        circuit_breaker: GeminiCircuitBreaker | None = None,
    ) -> None:
        self._generator = CommentaryGenerator(
            api_key=api_key, groq_api_key=groq_api_key or None, circuit_breaker=circuit_breaker,
        )
        self._qa_generator = QAGenerator(api_key=api_key, groq_api_key=groq_api_key or None)

        cartesia_api_key = os.environ.get("CARTESIA_API_KEY", "")
        if not cartesia_api_key:
            logger.warning(
                "CARTESIA_API_KEY not set -- TTS will degrade gracefully"
            )

        self._tts = TTSEngine(api_key=cartesia_api_key, voice_id=voice_id)
        # event_bus wired in setup() once available
        self._display = DisplayServer(host=display_host, port=display_port)

        self._event_bus: EventBus | None = None
        self._last_sanitized: SanitizedOutput | None = None
        self._last_quip_time: float = 0.0  # rate-limit injection reactions
        self._commentary_cancelled = asyncio.Event()
        self._sounds = SoundEffects()

    @property
    def display_server(self) -> DisplayServer:
        """Public access to the shared DisplayServer instance."""
        return self._display

    async def setup(self, event_bus: EventBus) -> None:
        """Wire into the event bus and start output components.

        Subscribes to observation_verified for automatic post-demo
        commentary and qa_requested for operator-triggered Q&A.
        Connects TTS engine and starts display server.

        Args:
            event_bus: The shared event bus from the capture pipeline.
        """
        self._event_bus = event_bus
        # Wire event_bus into TTS so it publishes tts_speaking/tts_finished
        # for audio capture mute coordination (Bug fix: was None before)
        self._tts._event_bus = event_bus
        event_bus.subscribe("observation_verified", self._on_observation_verified)
        event_bus.subscribe("qa_requested", self._on_qa_requested)
        event_bus.subscribe("injection_detected", self._on_injection_detected)
        event_bus.subscribe("demo_started", self._on_demo_started)
        event_bus.subscribe("demo_stopped", self._on_demo_stopped)

        # Connect TTS -- degrade gracefully on failure
        try:
            await self._tts.connect()
            default_health.mark_healthy("cartesia_tts")
        except Exception:
            logger.warning("TTS engine connection failed -- TTS will be unavailable", exc_info=True)
            default_health.mark_unhealthy("cartesia_tts")

        # Start display server -- degrade gracefully on failure
        try:
            await self._display.start()
            default_health.mark_healthy("display_server")
        except RuntimeError:
            logger.exception("Display server failed to start -- display will be unavailable")
            default_health.mark_unhealthy("display_server")

        logger.info("Commentary pipeline armed")

    async def _deliver_sentence(
        self,
        sentence: str,
        team_name: str,
        context_id: str,
        emotion: str,
        is_continuation: bool,
        sentence_index: int = 0,
    ) -> None:
        """Deliver a single sentence via TTS and display.

        Handles TTS health checking and graceful degradation to text-only
        mode if TTS is unavailable.

        Args:
            sentence: The sentence text to deliver.
            team_name: Team name for display context.
            context_id: Cartesia context ID for sentence grouping.
            emotion: Cartesia emotion tag for TTS.
            is_continuation: Whether this continues a prior context.
            sentence_index: Zero-based index of this sentence in the stream.
        """
        if default_health.is_healthy("cartesia_tts"):
            try:
                await asyncio.gather(
                    self._tts.speak(
                        sentence,
                        context_id,
                        emotion,
                        is_continuation=is_continuation,
                    ),
                    self._display.push_commentary(
                        sentence, team_name,
                        emotion=emotion,
                        sentence_index=sentence_index,
                    ),
                )
                # TTS succeeded -- mark healthy for future checks
                if self._tts._connected:
                    default_health.mark_healthy("cartesia_tts")
                else:
                    default_health.mark_unhealthy("cartesia_tts")
            except Exception:
                logger.exception("TTS speak failed, marking unhealthy")
                default_health.mark_unhealthy("cartesia_tts")
                # Still push text to display
                await self._display.push_commentary(
                    sentence, team_name,
                    emotion=emotion,
                    sentence_index=sentence_index,
                )
        else:
            # Text-only mode: TTS unhealthy, skip TTS and push to display only
            logger.info("TTS unhealthy -- delivering text-only commentary")
            await self._display.push_commentary(
                sentence, team_name,
                emotion=emotion,
                sentence_index=sentence_index,
            )

    async def _on_observation_verified(self, event: ObservationVerified) -> None:
        """Generate and deliver commentary after a demo stops.

        Uses sentence-level streaming for minimum latency: each sentence is
        spoken the moment it's detected in the LLM stream, while the model
        is still generating the next sentence. Falls back to batch mode
        when enrichment is enabled (enricher needs full text).

        CRITICAL: Always publishes CommentaryDelivered on completion or
        failure. The scoring pipeline waits for this event to trigger the
        theatrical score reveal — if we don't publish it, scores hang forever.
        """
        team_name = event.output.team_name
        full_text = ""
        _commentary_start = time.monotonic()

        # Clear cancellation flags from previous demo so new speaks work.
        # cancel() in _on_demo_started sets flags persistently — all
        # old queued speaks see them. We clear here because this is the
        # earliest point where new commentary will call speak().
        self._tts._cancelled.clear()
        self._commentary_cancelled.clear()

        # Declared outside the timeout scope so partial sentences survive
        # both inner and outer timeouts.
        sentences: list[str] = []

        try:
            async with asyncio.timeout(_PIPELINE_TIMEOUT):
                self._last_sanitized = event.output

                # Clear display before new commentary
                await self._display.clear()

                context_id = str(uuid.uuid4())[:8]

                # Always stream for minimum latency — speak each sentence the
                # moment it's detected in the LLM stream. Enrichment is skipped
                # in streaming mode because latency reduction > text polish.
                # Timeout prevents indefinite hangs from stalled LLM streams.
                # Both timeouts and mid-stream crashes are caught here so that
                # partial sentences are preserved in full_text.
                try:
                    async with asyncio.timeout(_COMMENTARY_TIMEOUT):
                        async for sentence, emotion, i in self._generator.stream_sentences(event.output):
                            if self._commentary_cancelled.is_set():
                                logger.info(
                                    "Commentary cancelled mid-stream for team %s "
                                    "after %d sentences", team_name, len(sentences),
                                )
                                break
                            sentences.append(sentence)
                            await self._deliver_sentence(
                                sentence, team_name, context_id,
                                emotion, is_continuation=(i > 0),
                                sentence_index=i,
                            )
                except TimeoutError:
                    logger.warning(
                        "Commentary generation timed out after %ds for team: %s "
                        "(delivered %d sentences before timeout)",
                        _COMMENTARY_TIMEOUT, team_name, len(sentences),
                    )
                except Exception:
                    logger.exception(
                        "Commentary streaming failed for team: %s "
                        "(delivered %d sentences before failure)",
                        team_name, len(sentences),
                    )
                full_text = " ".join(sentences)

                logger.info("Commentary delivered for team: %s", team_name)

        except TimeoutError:
            logger.warning(
                "Outer pipeline timeout (%ds) fired for team: %s — "
                "commentary handler took too long (inner timeout may have missed)",
                _PIPELINE_TIMEOUT, team_name,
            )
            full_text = " ".join(sentences)

        except Exception:
            logger.exception(
                "Commentary delivery failed for team: %s", team_name,
            )

        # Record commentary latency before publishing the delivered event.
        default_metrics.observe_seconds(
            "commentary.latency_sec", time.monotonic() - _commentary_start,
        )

        # ALWAYS publish — scoring pipeline depends on this event to
        # trigger the theatrical score reveal. Without it, scores hang.
        if self._event_bus is not None:
            self._event_bus.publish(
                CommentaryDelivered(
                    team_name=team_name,
                    commentary_text=full_text or "(commentary unavailable)",
                )
            )

    async def _on_qa_requested(self, event: QARequested) -> None:
        """Generate and deliver Q&A questions on operator command.

        Uses the last sanitized output to generate pointed questions,
        then speaks and displays each question.
        """
        try:
            if self._last_sanitized is None:
                logger.warning("Q&A requested but no demo data available")
                return

            team_name = self._last_sanitized.team_name
            questions = await self._qa_generator.generate(self._last_sanitized)

            context_id = str(uuid.uuid4())[:8]
            for i, question in enumerate(questions):
                # Use "neutral" as emotion for questions (safe fallback)
                if default_health.is_healthy("cartesia_tts"):
                    try:
                        await asyncio.gather(
                            self._tts.speak(
                                question.text,
                                context_id,
                                "neutral",
                                is_continuation=(i > 0),
                            ),
                            self._display.push_question(question.text, team_name),
                        )
                        if self._tts._connected:
                            default_health.mark_healthy("cartesia_tts")
                        else:
                            default_health.mark_unhealthy("cartesia_tts")
                    except Exception:
                        logger.exception("TTS speak failed during Q&A, marking unhealthy")
                        default_health.mark_unhealthy("cartesia_tts")
                        await self._display.push_question(question.text, team_name)
                else:
                    logger.info("TTS unhealthy -- delivering text-only Q&A")
                    await self._display.push_question(question.text, team_name)
                    # Delay between questions so audience can read each one
                    if i < len(questions) - 1:
                        await asyncio.sleep(8.0)

            logger.info("Q&A questions delivered for team: %s", team_name)

        except Exception:
            logger.exception("Q&A delivery failed")

    async def _on_demo_started(self, event: DemoStarted) -> None:
        """Cancel any in-flight TTS and commentary when a new demo begins.

        Cancels pending speak() calls AND signals the commentary streaming
        loop to stop, preventing old audio/text from bleeding into the new demo.
        """
        self._commentary_cancelled.set()
        self._tts.cancel()
        try:
            await self._tts.play_sound(self._sounds.start_chime)
        except Exception:
            logger.debug("Start chime playback failed", exc_info=True)

    async def _on_demo_stopped(self, event: DemoStopped) -> None:
        """Play stop tone when a demo ends."""
        try:
            await self._tts.play_sound(self._sounds.stop_tone)
        except Exception:
            logger.debug("Stop tone playback failed", exc_info=True)

    async def _on_injection_detected(self, event: InjectionDetected) -> None:
        """React to injection attempts in real-time with a spoken quip.

        Rate-limited to max one quip per 15 seconds to avoid overwhelming
        the audience. Uses pre-written quips for zero latency.
        """
        now = time.time()
        if now - self._last_quip_time < 15.0:
            return
        self._last_quip_time = now

        # Play alert sound then speak the quip
        try:
            await self._tts.play_sound(self._sounds.injection_alert)
        except Exception:
            pass

        quip = random.choice(_INJECTION_QUIPS)
        context_id = str(uuid.uuid4())[:8]
        try:
            await self._deliver_sentence(
                quip, "Arbiter", context_id, "sarcastic", is_continuation=False,
            )
            logger.info("Injection quip delivered: %s", quip[:60])
        except Exception:
            logger.debug("Injection quip delivery failed", exc_info=True)

    async def close(self) -> None:
        """Shut down generators, TTS engine, and display server."""
        await self._generator.close()
        await self._qa_generator.close()
        await self._tts.close()
        await self._display.stop()
