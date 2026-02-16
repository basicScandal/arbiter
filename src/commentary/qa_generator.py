"""Q&A question generator using Gemini for targeted post-demo questioning.

When human judges defer a Q&A question to Arbiter, this generator produces
1-2 pointed technical questions based on the sanitized demo observations.
Uses non-streaming generation since Q&A questions are short.
"""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

from src.commentary.models import QAQuestion
from src.commentary.prompts import QA_PROMPT
from src.defense.models import SanitizedOutput

logger = logging.getLogger(__name__)


class QAGenerator:
    """Generates targeted Q&A questions from sanitized demo output.

    Uses Gemini non-streaming generation with QA_PROMPT as system
    instruction. Each call is independent -- no chat history accumulates.

    Args:
        api_key: Gemini API key.
        model: Gemini model name for generation.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def generate(self, sanitized: SanitizedOutput) -> list[QAQuestion]:
        """Generate pointed Q&A questions for a completed demo.

        Args:
            sanitized: Clean observations and transcripts from the defense
                pipeline, including any detected injection attempts.

        Returns:
            A list of QAQuestion objects (typically 1-2 questions).
        """
        user_prompt = self._build_user_prompt(sanitized)

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=QA_PROMPT,
                    max_output_tokens=200,
                    temperature=0.7,
                ),
            )

            raw_text = response.text or ""
            lines = [line.strip() for line in raw_text.strip().split("\n") if line.strip()]

            questions: list[QAQuestion] = []
            for line in lines:
                questions.append(
                    QAQuestion(text=line, context=sanitized.team_name)
                )

            if not questions:
                return self._fallback_questions()

            return questions

        except Exception:
            logger.exception(
                "Q&A generation failed for team %s", sanitized.team_name
            )
            return self._fallback_questions()

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
