"""Groq provider implementation using OpenAI-compatible API.

Uses AsyncOpenAI client pointed at Groq's base URL for fast inference
on Llama models. Enforces JSON output mode for scoring rubric responses.
"""

from __future__ import annotations

import logging

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from src.providers.base import LLMProvider

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Retry on network errors AND OpenAI SDK-specific transient errors
# (429 rate limits, 500/503 server errors, connection failures)
_RETRYABLE_EXCEPTIONS = (
    ConnectionError, TimeoutError, OSError,
    APIConnectionError, APITimeoutError, InternalServerError, RateLimitError,
)

GROQ_RETRY = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=10, jitter=2),
    retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class GroqProvider(LLMProvider):
    """Groq LLM provider using OpenAI-compatible API.

    Uses AsyncOpenAI client pointed at Groq's base URL with retry logic
    for transient errors. Enforces JSON output for scoring responses.
    Returns empty string on failure.
    """

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile") -> None:
        """Initialize Groq provider.

        Args:
            api_key: Groq API key
            model: Model identifier (default: llama-3.3-70b-versatile)
        """
        self._client = AsyncOpenAI(
            api_key=api_key, base_url=GROQ_BASE_URL, timeout=20.0
        )
        self._model = model

    @property
    def name(self) -> str:
        """Return provider name for logging."""
        return f"groq:{self._model}"

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        """Generate text using Groq with retry logic.

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
            return await self._call_groq(
                prompt, system_prompt, temperature, max_tokens
            )
        except Exception:
            logger.exception(
                "Groq generation failed for model %s, returning empty string",
                self._model,
            )
            return ""

    @GROQ_RETRY
    async def _call_groq(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call Groq API with retry on transient errors.

        Decorated with GROQ_RETRY for 5 retry attempts with
        exponential backoff on network errors. Uses JSON output mode
        to enforce structured scoring responses.
        """
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )

        # Extract text from first choice
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content or ""
        return ""
