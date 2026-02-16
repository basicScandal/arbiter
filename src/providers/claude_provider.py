"""Claude provider implementation using anthropic SDK.

Uses AsyncAnthropic client for Claude Sonnet 4.5 with retry logic
for resilience against transient failures.
"""

from __future__ import annotations

import logging

from anthropic import (
    APIConnectionError,
    APITimeoutError,
    AsyncAnthropic,
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

# Retry on network errors AND Anthropic SDK-specific transient errors
# (429 rate limits, 500/503 server errors, connection failures)
_RETRYABLE_EXCEPTIONS = (
    ConnectionError, TimeoutError, OSError,
    APIConnectionError, APITimeoutError, InternalServerError, RateLimitError,
)

CLAUDE_RETRY = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=10, jitter=2),
    retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class ClaudeProvider(LLMProvider):
    """Claude LLM provider using anthropic SDK.

    Uses AsyncAnthropic client with retry logic for transient errors.
    Returns empty string on failure.
    """

    def __init__(
        self, api_key: str, model: str = "claude-sonnet-4-5-20250929"
    ) -> None:
        """Initialize Claude provider.

        Args:
            api_key: Anthropic API key
            model: Model identifier (default: claude-sonnet-4-5-20250929)
        """
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        """Return provider name for logging."""
        return f"claude:{self._model}"

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        """Generate text using Claude with retry logic.

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
            return await self._call_claude(
                prompt, system_prompt, temperature, max_tokens
            )
        except Exception:
            logger.exception(
                "Claude generation failed for model %s, returning empty string",
                self._model,
            )
            return ""

    @CLAUDE_RETRY
    async def _call_claude(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call Claude API with retry on transient errors.

        Decorated with CLAUDE_RETRY for 5 retry attempts with
        exponential backoff on network errors.
        """
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from first content block
        if message.content and len(message.content) > 0:
            return message.content[0].text
        return ""
