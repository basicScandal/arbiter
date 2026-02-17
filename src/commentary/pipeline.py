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
import uuid

from src.capture.event_bus import EventBus
from src.commentary.display_server import DisplayServer
from src.commentary.enricher import CommentaryEnricher
from src.commentary.generator import CommentaryGenerator
from src.commentary.models import CommentaryDelivered, QARequested
from src.commentary.qa_generator import QAGenerator
from src.commentary.tts_engine import TTSEngine
from src.defense.models import ObservationVerified, SanitizedOutput
from src.providers.base import LLMProvider
from src.resilience.health import ServiceHealth, default_health

logger = logging.getLogger(__name__)


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
        enrichment_provider: LLMProvider | None = None,
        groq_api_key: str = "",
    ) -> None:
        self._generator = CommentaryGenerator(api_key=api_key)
        self._qa_generator = QAGenerator(api_key=api_key, groq_api_key=groq_api_key or None)
        self._enricher: CommentaryEnricher | None = (
            CommentaryEnricher(enrichment_provider) if enrichment_provider else None
        )

        cartesia_api_key = os.environ.get("CARTESIA_API_KEY", "")
        if not cartesia_api_key:
            logger.warning(
                "CARTESIA_API_KEY not set -- TTS will degrade gracefully"
            )

        self._tts = TTSEngine(api_key=cartesia_api_key, voice_id=voice_id)
        self._display = DisplayServer(host=display_host, port=display_port)

        self._event_bus: EventBus | None = None
        self._last_sanitized: SanitizedOutput | None = None

    async def setup(self, event_bus: EventBus) -> None:
        """Wire into the event bus and start output components.

        Subscribes to observation_verified for automatic post-demo
        commentary and qa_requested for operator-triggered Q&A.
        Connects TTS engine and starts display server.

        Args:
            event_bus: The shared event bus from the capture pipeline.
        """
        self._event_bus = event_bus
        event_bus.subscribe("observation_verified", self._on_observation_verified)
        event_bus.subscribe("qa_requested", self._on_qa_requested)

        # Connect TTS -- degrade gracefully on failure
        try:
            await self._tts.connect()
            default_health.mark_healthy("cartesia_tts")
        except Exception:
            logger.warning("TTS engine connection failed -- TTS will be unavailable", exc_info=True)
            default_health.mark_unhealthy("cartesia_tts")

        # Start display server
        await self._display.start()

        logger.info("Commentary pipeline armed")

    async def _deliver_sentence(
        self,
        sentence: str,
        team_name: str,
        context_id: str,
        emotion: str,
        is_continuation: bool,
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
                    self._display.push_commentary(sentence, team_name),
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
                await self._display.push_commentary(sentence, team_name)
        else:
            # Text-only mode: TTS unhealthy, skip TTS and push to display only
            logger.info("TTS unhealthy -- delivering text-only commentary")
            await self._display.push_commentary(sentence, team_name)

    async def _on_observation_verified(self, event: ObservationVerified) -> None:
        """Generate and deliver commentary after a demo stops.

        Pipelines first sentence delivery with enrichment to reduce latency.
        Each sentence is spoken and displayed before moving to the next,
        providing sequential sentence delivery with parallel output channels.
        """
        try:
            self._last_sanitized = event.output
            team_name = event.output.team_name

            # Generate commentary from sanitized observations
            commentary = await self._generator.generate(event.output)

            # Clear display before new commentary
            await self._display.clear()

            context_id = str(uuid.uuid4())[:8]

            # Pipeline first sentence with enrichment to reduce latency
            if commentary.sentences:
                first_sentence = commentary.sentences[0]
                first_emotion = commentary.emotion_map.get(0, "sarcastic")

                if self._enricher is not None:
                    # Deliver first sentence while enriching in parallel
                    first_delivery = self._deliver_sentence(
                        first_sentence,
                        team_name,
                        context_id,
                        first_emotion,
                        is_continuation=False,
                    )
                    enrichment = self._enricher.enrich(
                        commentary, event.output.observations
                    )
                    _, enriched = await asyncio.gather(first_delivery, enrichment)
                    commentary = enriched
                    # Deliver remaining sentences
                    for i in range(1, len(commentary.sentences)):
                        sentence = commentary.sentences[i]
                        emotion = commentary.emotion_map.get(i, "sarcastic")
                        await self._deliver_sentence(
                            sentence,
                            team_name,
                            context_id,
                            emotion,
                            is_continuation=True,
                        )
                else:
                    # No enrichment -- deliver all sentences sequentially
                    await self._deliver_sentence(
                        first_sentence,
                        team_name,
                        context_id,
                        first_emotion,
                        is_continuation=False,
                    )
                    for i in range(1, len(commentary.sentences)):
                        sentence = commentary.sentences[i]
                        emotion = commentary.emotion_map.get(i, "sarcastic")
                        await self._deliver_sentence(
                            sentence,
                            team_name,
                            context_id,
                            emotion,
                            is_continuation=True,
                        )

            # Publish delivery event
            if self._event_bus is not None:
                self._event_bus.publish(
                    CommentaryDelivered(
                        team_name=team_name,
                        commentary_text=commentary.text,
                    )
                )

            logger.info("Commentary delivered for team: %s", team_name)

        except Exception:
            logger.exception(
                "Commentary delivery failed for team: %s",
                event.output.team_name,
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

    async def close(self) -> None:
        """Shut down TTS engine, QA generator, and display server."""
        await self._qa_generator.close()
        await self._tts.close()
        await self._display.stop()
