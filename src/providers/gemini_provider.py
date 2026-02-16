"""Gemini provider implementation using google-genai SDK.

Wraps the existing Gemini client pattern from scoring/engine.py.
Uses tenacity retry decorator for resilience.
"""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

from src.providers.base import LLMProvider
from src.resilience.retry import GEMINI_RETRY_BACKGROUND

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Gemini LLM provider using google-genai SDK.

    Uses the same client pattern as ScoringEngine with retry logic
    for transient network errors. Returns empty string on failure.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        """Initialize Gemini provider.

        Args:
            api_key: Google API key for Gemini
            model: Model identifier (default: gemini-2.5-flash)
        """
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        """Return provider name for logging."""
        return f"gemini:{self._model}"

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        """Generate text using Gemini with retry logic.

        Retries transient network errors up to 5 times with exponential
        backoff. Returns empty string on any failure.

        Args:
            prompt: User prompt content
            system_prompt: System instruction
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum output tokens

        Returns:
            Generated text or empty string on failure
        """
        try:
            return await self._call_gemini(
                prompt, system_prompt, temperature, max_tokens
            )
        except Exception:
            logger.exception(
                "Gemini generation failed for model %s, returning empty string",
                self._model,
            )
            return ""

    @GEMINI_RETRY_BACKGROUND
    async def _call_gemini(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call Gemini API with retry on transient errors.

        Decorated with GEMINI_RETRY_BACKGROUND for 5 retry attempts
        with exponential backoff on network errors.
        """
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens,
                temperature=temperature,
                # Disable thinking for structured output -- thinking tokens
                # consume max_output_tokens budget, truncating JSON responses
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return response.text or ""
