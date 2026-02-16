"""Async streaming commentary generation via Gemini P-LLM.

Accepts SanitizedOutput from the defense pipeline and produces a
Commentary object with sentence-level breakdown and emotion mapping
for downstream TTS and display consumption.
"""

from __future__ import annotations

import logging
import re
import time

from google import genai
from google.genai import types

from src.commentary.models import Commentary
from src.commentary.prompts import PERSONA_PROMPT
from src.defense.models import SanitizedOutput
from src.resilience.retry import GEMINI_RETRY

logger = logging.getLogger(__name__)

# Keyword map for 12 emotion tags used by Cartesia TTS.
# Each key is a Cartesia emotion, value is a list of trigger phrases.
# First matching emotion wins (dict insertion order).
_EMOTION_KEYWORDS: dict[str, list[str]] = {
    "sarcastic": ["bold strategy", "interesting choice", "somehow", "mysteriously", "apparently", "of course"],
    "ironic": ["ironic", "irony", "ironically", "paradox"],
    "contempt": ["pathetic", "embarrassing", "lazy", "half-baked", "amateur"],
    "surprised": ["actually", "genuinely", "surprisingly", "didn't expect", "impressed", "wow"],
    "amazed": ["incredible", "remarkable", "exceptional", "brilliant", "stunning"],
    "disappointed": ["unfortunately", "shame", "disaster", "terrible", "awful", "missing", "broken", "failed", "crashed"],
    "content": ["solid", "clean", "elegant", "respect", "well-built", "thoughtful"],
    "excited": ["love", "amazing", "fantastic", "breakthrough"],
    "confident": ["clearly the best", "no question", "without doubt", "winner"],
    "skeptical": ["claims", "supposedly", "allegedly", "in theory", "if we believe", "questionable"],
    "curious": ["interesting", "intriguing", "wonder", "how did"],
    "proud": ["now that", "that's what", "exactly right", "nailed"],
}


class CommentaryGenerator:
    """Generates streaming commentary for a demo via Gemini.

    Each call to generate() makes a fresh generate_content_stream request
    with the full PERSONA_PROMPT as system_instruction. No chat history
    is accumulated between demos, preventing persona drift.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def generate(self, sanitized: SanitizedOutput) -> Commentary:
        """Generate commentary for a completed demo.

        Args:
            sanitized: Clean observations and transcripts from the defense
                pipeline, including any detected injection attempts.

        Returns:
            A Commentary object with full text, sentence breakdown, and
            per-sentence emotion mapping for TTS.
        """
        user_prompt = self._build_user_prompt(sanitized)

        try:
            full_text = await self._stream_gemini(user_prompt)
        except Exception:
            logger.exception("Commentary generation failed for team %s", sanitized.team_name)
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

    @GEMINI_RETRY
    async def _stream_gemini(self, user_prompt: str) -> str:
        """Stream commentary text from Gemini with retry on transient errors.

        Retries up to 3 times with exponential backoff + jitter on network
        errors. Non-retryable errors propagate to generate() fallback logic.
        """
        full_text = ""
        async for chunk in await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=PERSONA_PROMPT,
                max_output_tokens=500,
                temperature=0.8,
            ),
        ):
            if chunk.text:
                full_text += chunk.text
        return full_text

    def _build_user_prompt(self, sanitized: SanitizedOutput) -> str:
        """Build the user prompt from sanitized demo output.

        Structures observations, transcripts, and injection attempts
        into a clear format for the persona to react to.
        """
        sections: list[str] = [f"## Demo: {sanitized.team_name}"]

        # Observations
        if sanitized.observations:
            obs_lines = [f"{i + 1}. {obs}" for i, obs in enumerate(sanitized.observations)]
            sections.append("### Observations\n" + "\n".join(obs_lines))

        # Transcript highlights
        if sanitized.transcripts:
            sections.append("### Transcript Highlights\n" + "\n".join(sanitized.transcripts))

        # Duration
        sections.append(f"### Duration\n{sanitized.demo_duration:.0f}s")

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
