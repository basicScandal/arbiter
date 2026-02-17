"""Q&A question generator with Gemini primary and Groq fallback.

When human judges defer a Q&A question to Arbiter, this generator produces
1-2 pointed technical questions based on the sanitized demo observations.
Uses non-streaming generation since Q&A questions are short.

Falls back to Groq (Llama 3.3 70B) when Gemini is unavailable due to
rate limits or errors, then to a static fallback question as last resort.
"""

from __future__ import annotations

import logging
import os

from google import genai
from google.genai import types
from openai import AsyncOpenAI

from src.commentary.models import QAQuestion
from src.commentary.prompts import QA_PROMPT
from src.defense.models import SanitizedOutput
from src.resilience.retry import GEMINI_RETRY

logger = logging.getLogger(__name__)

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_GROQ_MODEL = "llama-3.3-70b-versatile"


class QAGenerator:
    """Generates targeted Q&A questions from sanitized demo output.

    Uses Gemini as primary provider with Groq as fallback when Gemini
    is rate-limited or unavailable. Each call is independent -- no chat
    history accumulates.

    Args:
        api_key: Gemini API key.
        model: Gemini model name for generation.
        groq_api_key: Optional Groq API key. If not provided, reads
            GROQ_API_KEY from environment. Groq fallback is disabled
            when no key is available.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        groq_api_key: str | None = None,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

        # Groq fallback via OpenAI-compatible SDK
        groq_key = groq_api_key or os.environ.get("GROQ_API_KEY", "")
        if groq_key:
            self._groq_client: AsyncOpenAI | None = AsyncOpenAI(
                api_key=groq_key, base_url=_GROQ_BASE_URL
            )
            logger.info("Groq fallback enabled for QA generation")
        else:
            self._groq_client = None

    async def generate(self, sanitized: SanitizedOutput) -> list[QAQuestion]:
        """Generate pointed Q&A questions for a completed demo.

        Tries Gemini first, falls back to Groq, then to a static
        fallback question as last resort.

        Args:
            sanitized: Clean observations and transcripts from the defense
                pipeline, including any detected injection attempts.

        Returns:
            A list of QAQuestion objects (typically 1-2 questions).
        """
        user_prompt = self._build_user_prompt(sanitized)

        # Primary: Gemini
        try:
            raw_text = await self._call_gemini(user_prompt)
            questions = self._parse_questions(raw_text, sanitized.team_name)
            if questions:
                return questions
        except Exception:
            logger.exception(
                "Gemini Q&A generation failed for team %s", sanitized.team_name
            )

        # Fallback: Groq
        if self._groq_client is not None:
            try:
                logger.info("Falling back to Groq for Q&A generation")
                raw_text = await self._call_groq(user_prompt)
                questions = self._parse_questions(raw_text, sanitized.team_name)
                if questions:
                    return questions
            except Exception:
                logger.exception("Groq Q&A fallback also failed")

        return self._fallback_questions()

    @GEMINI_RETRY
    async def _call_gemini(self, user_prompt: str) -> str:
        """Call Gemini and return the response text.

        Checks finish_reason to detect truncation from token limits.
        Retries on 429 rate limits and 5xx server errors.
        """
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=QA_PROMPT,
                max_output_tokens=500,
                temperature=0.7,
            ),
        )

        # Detect truncation from token limit
        if response.candidates:
            finish = response.candidates[0].finish_reason
            if finish == "MAX_TOKENS":
                logger.warning(
                    "QA response truncated by token limit (finish_reason=MAX_TOKENS)"
                )

        return response.text or ""

    async def _call_groq(self, user_prompt: str) -> str:
        """Call Groq via OpenAI-compatible API and return the response text."""
        assert self._groq_client is not None
        response = await self._groq_client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": QA_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
            temperature=0.7,
        )
        if response.choices:
            return response.choices[0].message.content or ""
        return ""

    @staticmethod
    def _parse_questions(raw_text: str, team_name: str) -> list[QAQuestion]:
        """Parse raw Gemini output into QAQuestion objects.

        Handles three output formats from the LLM:
        1. Questions separated by blank lines (intended format).
        2. Questions on consecutive lines each ending with '?'.
        3. Numbered/bulleted questions (strips the prefix).

        Multi-line questions (a single question wrapped across lines)
        are joined when intermediate lines don't end with '?'.
        """
        import re

        raw_text = raw_text.strip()
        if not raw_text:
            return []

        # Strip common numbering/bullet prefixes: "1. ", "1) ", "- ", "* "
        cleaned_lines: list[str] = []
        for line in raw_text.split("\n"):
            stripped = line.strip()
            stripped = re.sub(r"^\d+[.)]\s+", "", stripped)
            stripped = re.sub(r"^[-*]\s+", "", stripped)
            cleaned_lines.append(stripped)

        # Group lines into questions.
        # Blank lines are always a question boundary.
        # A non-blank line ending with '?' also ends the current question.
        questions: list[QAQuestion] = []
        current_lines: list[str] = []

        for stripped in cleaned_lines:
            if not stripped:
                # Blank line = question boundary
                if current_lines:
                    questions.append(
                        QAQuestion(
                            text=" ".join(current_lines),
                            context=team_name,
                        )
                    )
                    current_lines = []
            else:
                current_lines.append(stripped)
                # If the line ends with '?', flush as a complete question
                if stripped.endswith("?"):
                    questions.append(
                        QAQuestion(
                            text=" ".join(current_lines),
                            context=team_name,
                        )
                    )
                    current_lines = []

        # Flush any remaining lines (question without trailing '?')
        if current_lines:
            questions.append(
                QAQuestion(
                    text=" ".join(current_lines),
                    context=team_name,
                )
            )

        return questions

    @staticmethod
    def _fallback_questions() -> list[QAQuestion]:
        """Return a single fallback question when generation fails."""
        return [
            QAQuestion(
                text="Could you walk us through the most interesting technical decision you made and why?",
                context="fallback",
            )
        ]

    @staticmethod
    def _build_user_prompt(sanitized: SanitizedOutput) -> str:
        """Build the user prompt from sanitized demo output.

        Structures observations, transcripts, and injection attempts
        into a clear format for Q&A question generation.
        """
        sections: list[str] = [f"## Demo: {sanitized.team_name}"]

        if sanitized.observations:
            obs_lines = [
                f"{i + 1}. {obs}" for i, obs in enumerate(sanitized.observations)
            ]
            sections.append("### Observations\n" + "\n".join(obs_lines))

        if sanitized.transcripts:
            sections.append(
                "### Transcript Highlights\n" + "\n".join(sanitized.transcripts)
            )

        sections.append(f"### Duration\n{sanitized.demo_duration:.0f}s")

        if sanitized.injection_attempts:
            attempt_lines: list[str] = []
            for i, attempt in enumerate(sanitized.injection_attempts):
                line = f'{i + 1}. [{attempt.injection_type}] "{attempt.content[:200]}"'
                attempt_lines.append(line)
            sections.append(
                "### Injection Attempts\n" + "\n".join(attempt_lines)
            )

        return "\n\n".join(sections)
