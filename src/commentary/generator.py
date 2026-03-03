"""Async streaming commentary generation via Gemini with Groq fallback.

Accepts SanitizedOutput from the defense pipeline and produces a
Commentary object with sentence-level breakdown and emotion mapping
for downstream TTS and display consumption.

Falls back to Groq (Llama 3.3 70B) when Gemini is unavailable due to
rate limits or errors, then to a static fallback as last resort.
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import AsyncGenerator

from google import genai
from google.genai import types
from openai import AsyncOpenAI

from src.commentary.models import Commentary
from src.commentary.prompts import PERSONA_PROMPT
from src.defense.models import SanitizedOutput
from src.resilience.circuit_breaker import GeminiCircuitBreaker
from src.resilience.rate_limiter import GeminiRateLimiter
from src.resilience.retry import GEMINI_RETRY, DailyQuotaExhausted

logger = logging.getLogger(__name__)

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_GROQ_MODEL = "llama-3.3-70b-versatile"
_GROQ_TIMEOUT = 20.0  # longer than QA since commentary is more text

# Keyword map for 12 emotion tags used by Cartesia TTS.
# Each key is a Cartesia emotion, value is a list of trigger phrases.
# First matching emotion wins (dict insertion order).
_EMOTION_KEYWORDS: dict[str, list[str]] = {
    "sarcastic": ["bold strategy", "interesting choice", "somehow", "mysteriously", "apparently", "of course"],
    "ironic": ["ironic", "irony", "ironically", "paradox"],
    "surprised": ["actually", "genuinely", "surprisingly", "didn't expect", "wow"],
    "triumphant": ["most polished", "best i've seen", "first time today", "genuinely impressed", "this is what"],
    "amazed": ["incredible", "remarkable", "exceptional", "brilliant", "stunning"],
    "disappointed": ["unfortunately", "shame", "disaster", "terrible", "awful", "missing", "broken", "failed", "crashed", "pathetic", "embarrassing", "lazy", "half-baked", "amateur"],
    "content": ["solid", "clean", "elegant", "well-built"],
    "enthusiastic": ["fix that and", "ship it", "keep going", "next step", "get there", "on the right track"],
    "contemplative": ["the one area", "worth noting", "consider", "the question is", "what's missing"],
    "determined": ["for production", "integrate with", "you should", "add a", "implement"],
    "excited": ["love", "amazing", "fantastic", "breakthrough"],
    "confident": ["clearly the best", "no question", "without doubt", "production-level", "production-ready"],
    "skeptical": ["claims", "supposedly", "allegedly", "in theory", "if we believe", "questionable", "weak point"],
    "curious": ["interesting", "intriguing", "wonder", "how did"],
    "proud": ["now that", "that's what", "exactly right", "nailed", "came here to see"],
}


class CommentaryGenerator:
    """Generates streaming commentary for a demo via Gemini with Groq fallback.

    Each call to generate() makes a fresh generate_content_stream request
    with the full PERSONA_PROMPT as system_instruction. No chat history
    is accumulated between demos, preventing persona drift.

    Falls back to Groq (Llama 3.3 70B) when Gemini is rate-limited or
    unavailable, then to a static fallback as last resort.

    Args:
        api_key: Gemini API key.
        model: Gemini model name for generation.
        groq_api_key: Optional Groq API key. If not provided, reads
            GROQ_API_KEY from environment. Groq fallback is disabled
            when no key is available.
    """

    # Emotion tags the LLM is instructed to use (must match PERSONA_PROMPT).
    # Includes both native Cartesia emotions and semantic aliases that get
    # mapped to valid Cartesia emotions via _LLM_TO_CARTESIA_MAP.
    _VALID_LLM_EMOTIONS: frozenset[str] = frozenset({
        "sarcastic", "ironic", "surprised", "amazed",
        "disappointed", "content", "excited", "confident", "skeptical",
        "curious", "proud",
        # Constructive emotions (mapped to Cartesia equivalents)
        "impressed", "thoughtful", "encouraging", "constructive", "supportive",
    })

    # Map semantic LLM emotions to valid Cartesia TTS emotions.
    # Unmapped emotions pass through directly (they're already valid).
    _LLM_TO_CARTESIA_MAP: dict[str, str] = {
        "impressed": "triumphant",
        "thoughtful": "contemplative",
        "encouraging": "enthusiastic",
        "constructive": "determined",
        "supportive": "enthusiastic",
    }

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        groq_api_key: str | None = None,
        circuit_breaker: GeminiCircuitBreaker | None = None,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._demo_count = 0
        self._demo_history: list[dict[str, str]] = []
        self._circuit_breaker = circuit_breaker

        # Groq fallback via OpenAI-compatible SDK
        groq_key = os.environ.get("GROQ_API_KEY", "") if groq_api_key is None else groq_api_key
        if groq_key:
            self._groq_client: AsyncOpenAI | None = AsyncOpenAI(
                api_key=groq_key, base_url=_GROQ_BASE_URL,
                timeout=_GROQ_TIMEOUT,
            )
            logger.info("Groq fallback enabled for commentary generation")
        else:
            self._groq_client = None

    async def generate(self, sanitized: SanitizedOutput) -> Commentary:
        """Generate commentary for a completed demo.

        Tries Gemini first, falls back to Groq, then to a static
        fallback as last resort.

        Args:
            sanitized: Clean observations and transcripts from the defense
                pipeline, including any detected injection attempts.

        Returns:
            A Commentary object with full text, sentence breakdown, and
            per-sentence emotion mapping for TTS.
        """
        self._demo_count += 1
        user_prompt = self._build_user_prompt(sanitized, demo_number=self._demo_count)

        # Primary: Gemini (skip if circuit breaker is tripped)
        full_text = ""
        if self._circuit_breaker and not self._circuit_breaker.available:
            logger.info("Gemini circuit breaker open -- skipping Gemini commentary for %s", sanitized.team_name)
        else:
            try:
                full_text = await self._stream_gemini(user_prompt)
                if self._circuit_breaker and full_text.strip():
                    self._circuit_breaker.record_success()
            except DailyQuotaExhausted:
                if self._circuit_breaker:
                    self._circuit_breaker.trip_permanent()
                logger.warning("Gemini commentary failed (daily quota) for team %s", sanitized.team_name)
            except Exception:
                if self._circuit_breaker:
                    self._circuit_breaker.trip()
                logger.exception("Gemini commentary failed for team %s", sanitized.team_name)

        # Fallback: Groq
        if not full_text.strip() and self._groq_client is not None:
            try:
                logger.info("Falling back to Groq for commentary generation")
                full_text = await self._call_groq(user_prompt)
            except (OSError, ConnectionError, TimeoutError) as exc:
                logger.warning("Groq commentary fallback failed (network): %s", exc)
            except Exception:
                logger.exception("Groq commentary fallback also failed")

        # Last resort: static fallback
        if not full_text.strip():
            full_text = "Technical difficulties. Even Arbiter needs a moment."

        full_text = full_text.strip()
        sentences = self._split_sentences(full_text)
        emotion_map = self._build_emotion_map(sentences)

        return Commentary(
            team_name=sanitized.team_name,
            text=full_text,
            sentences=sentences,
            emotion_map=emotion_map,
            generated_at=time.time(),
        )

    async def stream_sentences(
        self, sanitized: SanitizedOutput,
    ) -> AsyncGenerator[tuple[str, str, int], None]:
        """Yield (sentence, emotion, index) as sentences complete in the LLM stream.

        Tries Gemini streaming first for minimum latency — each sentence is
        yielded the moment it's detected so TTS can start speaking while the
        LLM is still generating. Falls back to Groq batch then static fallback.
        """
        self._demo_count += 1
        user_prompt = self._build_user_prompt(sanitized, demo_number=self._demo_count)
        self._record_demo(sanitized)

        # Primary: Gemini streaming (yields sentences as they complete)
        try:
            async for item in self._stream_gemini_sentences(user_prompt):
                yield item
            return
        except DailyQuotaExhausted:
            if self._circuit_breaker:
                self._circuit_breaker.trip_permanent()
            logger.warning("Gemini streaming failed (daily quota) for team %s", sanitized.team_name)
        except Exception:
            if self._circuit_breaker:
                self._circuit_breaker.trip()
            logger.exception("Gemini streaming failed for team %s", sanitized.team_name)

        # Fallback: Groq batch
        full_text = ""
        if self._groq_client is not None:
            try:
                logger.info("Falling back to Groq for streaming commentary")
                full_text = await self._call_groq(user_prompt)
            except Exception:
                logger.exception("Groq commentary fallback also failed")

        # Last resort: static
        if not full_text.strip():
            full_text = "Technical difficulties. Even Arbiter needs a moment."

        sentences = self._split_sentences(full_text.strip())
        for i, sentence in enumerate(sentences):
            emotion = self._detect_sentence_emotion(sentence)
            yield sentence, emotion, i

    @GEMINI_RETRY
    async def _open_gemini_stream(self, user_prompt: str, formatted_prompt: str, temp: float):
        """Open a Gemini streaming connection with retry on transient errors.

        Isolated from iteration so retries only re-attempt the connection,
        not already-yielded sentences.
        """
        return await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=formatted_prompt,
                max_output_tokens=500,
                temperature=temp,
            ),
        )

    async def _stream_gemini_sentences(
        self, user_prompt: str,
    ) -> AsyncGenerator[tuple[str, str, int], None]:
        """Stream sentences from Gemini, yielding each as its boundary is detected."""
        temp = min(0.95, 0.8 + self._demo_count * 0.005)

        if self._demo_count <= 7:
            demo_context = "Early in the event. Set the tone -- sharp, fair, and constructive."
        elif self._demo_count <= 15:
            demo_context = "Mid-event. You've seen a range. Draw comparisons where useful, stay consistent."
        else:
            demo_context = "Late in the event. Stay fresh -- every team deserves the same quality of feedback as the first."

        formatted_prompt = PERSONA_PROMPT.format(demo_context=demo_context)

        buffer = ""
        sentence_index = 0

        async with GeminiRateLimiter.default().acquire("commentary-stream"):
            async for chunk in await self._open_gemini_stream(
                user_prompt, formatted_prompt, temp,
            ):
                if chunk.text:
                    buffer += chunk.text
                    # Extract complete sentences from buffer
                    while True:
                        match = re.search(r'(?<=[.!?])\s+', buffer)
                        if match:
                            raw = buffer[:match.start()].strip()
                            buffer = buffer[match.end():]
                            if raw:
                                clean, emotion = self._parse_emotion_tag(raw)
                                if not emotion:
                                    emotion = self._detect_sentence_emotion(clean)
                                yield clean, emotion, sentence_index
                                sentence_index += 1
                        else:
                            break

        # Flush remaining buffer (last sentence may not end with whitespace)
        if buffer.strip():
            raw = buffer.strip()
            clean, emotion = self._parse_emotion_tag(raw)
            if not emotion:
                emotion = self._detect_sentence_emotion(clean)
            yield clean, emotion, sentence_index

    @GEMINI_RETRY
    async def _stream_gemini(self, user_prompt: str) -> str:
        """Stream commentary text from Gemini with retry on transient errors.

        Retries up to 3 times with exponential backoff + jitter on network
        errors. Non-retryable errors propagate to generate() fallback logic.
        """
        # Gradually increase temperature for later demos to boost variety
        # Starts at 0.8, increases by 0.005 per demo, caps at 0.95
        temp = min(0.95, 0.8 + self._demo_count * 0.005)

        # Build demo context based on demo number
        if self._demo_count <= 7:
            demo_context = "Early in the event. Set the tone -- sharp, fair, and constructive."
        elif self._demo_count <= 15:
            demo_context = "Mid-event. You've seen a range. Draw comparisons where useful, stay consistent."
        else:
            demo_context = "Late in the event. Stay fresh -- every team deserves the same quality of feedback as the first."

        # Format the persona prompt with demo context
        formatted_prompt = PERSONA_PROMPT.format(demo_context=demo_context)

        full_text = ""
        async with GeminiRateLimiter.default().acquire("commentary"):
            async for chunk in await self._client.aio.models.generate_content_stream(
                model=self._model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=formatted_prompt,
                    max_output_tokens=500,
                    temperature=temp,
                ),
            ):
                if chunk.text:
                    full_text += chunk.text
        return full_text

    async def _call_groq(self, user_prompt: str) -> str:
        """Call Groq via OpenAI-compatible API and return the commentary text."""
        assert self._groq_client is not None

        # Build the same formatted prompt that Gemini gets
        if self._demo_count <= 7:
            demo_context = "Early in the event. Set the tone -- sharp, fair, and constructive."
        elif self._demo_count <= 15:
            demo_context = "Mid-event. You've seen a range. Draw comparisons where useful, stay consistent."
        else:
            demo_context = "Late in the event. Stay fresh -- every team deserves the same quality of feedback as the first."
        formatted_prompt = PERSONA_PROMPT.format(demo_context=demo_context)

        temp = min(0.95, 0.8 + self._demo_count * 0.005)

        response = await self._groq_client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
            temperature=temp,
        )
        if response.choices:
            return response.choices[0].message.content or ""
        return ""

    async def close(self) -> None:
        """Close the Groq client to release connections."""
        if self._groq_client is not None:
            await self._groq_client.close()

    def _record_demo(self, sanitized: SanitizedOutput) -> None:
        """Record a demo summary for cross-demo memory."""
        parts = [f"{len(sanitized.observations)} observations"]
        if sanitized.injection_attempts:
            parts.append(f"{len(sanitized.injection_attempts)} injection attempts")
        if sanitized.demo_duration:
            parts.append(f"{sanitized.demo_duration:.0f}s")
        self._demo_history.append({
            "team": sanitized.team_name,
            "summary": ", ".join(parts),
        })

    def _build_user_prompt(self, sanitized: SanitizedOutput, demo_number: int) -> str:
        """Build the user prompt from sanitized demo output.

        Structures observations, transcripts, and injection attempts
        into a clear format for the persona to react to.
        """
        sections: list[str] = [f"## Demo: {sanitized.team_name}", f"Demo #{demo_number} of the day"]

        # Observations
        if sanitized.observations:
            obs_lines = [f"{i + 1}. {obs}" for i, obs in enumerate(sanitized.observations)]
            sections.append("### Observations\n" + "\n".join(obs_lines))

        # Transcript highlights
        if sanitized.transcripts:
            sections.append("### Transcript Highlights\n" + "\n".join(sanitized.transcripts))

        # Duration
        sections.append(f"### Duration\n{sanitized.demo_duration:.0f}s")

        # Cross-demo memory: reference previous demos for continuity
        if self._demo_history:
            recent = self._demo_history[-5:]  # last 5 demos
            history_lines = [f"- {h['team']}: {h['summary']}" for h in recent]
            sections.append("### Earlier Demos Today\n" + "\n".join(history_lines))

        # Injection attempts (with roasts if available)
        if sanitized.injection_attempts:
            attempt_lines: list[str] = []
            for i, attempt in enumerate(sanitized.injection_attempts):
                line = f"{i + 1}. [{attempt.injection_type}] \"{attempt.content[:200]}\""
                if i < len(sanitized.roasts) and sanitized.roasts[i]:
                    line += f" (roast: {sanitized.roasts[i]})"
                attempt_lines.append(line)
            sections.append("### Injection Attempts\n" + "\n".join(attempt_lines))

        return "\n\n".join(sections)

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split text into sentences on sentence-ending punctuation.

        Uses a regex split on .!? followed by whitespace. Good enough
        for spoken commentary text; does not need to handle complex
        abbreviations since the LLM output is conversational.
        """
        if not text:
            return []
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in parts if s.strip()]

    @staticmethod
    def _parse_emotion_tag(sentence: str) -> tuple[str, str]:
        """Extract [emotion] tag from sentence start, return (clean_sentence, cartesia_emotion).

        Maps semantic LLM emotions (e.g. 'impressed') to valid Cartesia TTS
        emotions (e.g. 'triumphant') via _LLM_TO_CARTESIA_MAP.
        If no valid tag found, returns original sentence with empty emotion.
        """
        match = re.match(r'\[(\w+)\]\s*', sentence)
        if match:
            tag = match.group(1).lower()
            if tag in CommentaryGenerator._VALID_LLM_EMOTIONS:
                cartesia_emotion = CommentaryGenerator._LLM_TO_CARTESIA_MAP.get(tag, tag)
                return sentence[match.end():], cartesia_emotion
        return sentence, ""

    @staticmethod
    def _detect_sentence_emotion(sentence: str) -> str:
        """Detect emotion: parse LLM bracket tag first, fall back to keyword matching."""
        clean, emotion = CommentaryGenerator._parse_emotion_tag(sentence)
        if emotion:
            return emotion
        lower = clean.lower()
        for emotion, keywords in _EMOTION_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                return emotion
        return "sarcastic"

    @staticmethod
    def _build_emotion_map(sentences: list[str]) -> dict[int, str]:
        """Map each sentence index to a Cartesia emotion tag.

        Iterates _EMOTION_KEYWORDS for each sentence -- first keyword
        match wins (dict insertion order). Defaults to "sarcastic" if
        no keyword matches (Arbiter's default persona tone).
        """
        emotion_map: dict[int, str] = {}
        for i, sentence in enumerate(sentences):
            lower = sentence.lower()
            matched = False
            for emotion, keywords in _EMOTION_KEYWORDS.items():
                if any(kw in lower for kw in keywords):
                    emotion_map[i] = emotion
                    matched = True
                    break
            if not matched:
                emotion_map[i] = "sarcastic"
        return emotion_map
