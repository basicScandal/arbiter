"""OpenAI provider implementation using openai SDK.

Uses AsyncOpenAI client for GPT-4o with retry logic for resilience
against transient failures.
"""

from __future__ import annotations

import logging

from src.config.models import OPENAI_MODEL
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

# Retry on network errors AND OpenAI SDK-specific transient errors
# (429 rate limits, 500/503 server errors, connection failures)
_RETRYABLE_EXCEPTIONS = (
    ConnectionError, TimeoutError, OSError,
    APIConnectionError, APITimeoutError, InternalServerError, RateLimitError,
)

OPENAI_RETRY = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=10, jitter=2),
    retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider using openai SDK.

    Uses AsyncOpenAI client with retry logic for transient errors.
    Returns empty string on failure.
    """

    def __init__(self, api_key: str, model: str = OPENAI_MODEL) -> None:
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model identifier (default: gpt-4o)
        """
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        """Return provider name for logging."""
        return f"openai:{self._model}"

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        """Generate text using OpenAI with retry logic.

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
            return await self._call_openai(
                prompt, system_prompt, temperature, max_tokens
            )
        except Exception:
            logger.exception(
                "OpenAI generation failed for model %s, returning empty string",
                self._model,
            )
            return ""

    @OPENAI_RETRY
    async def _call_openai(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call OpenAI API with retry on transient errors.

        Decorated with OPENAI_RETRY for 5 retry attempts with
        exponential backoff on network errors.
        """
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )

        # Extract text from first choice
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content or ""
        return ""
