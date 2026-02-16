"""Base provider interface for multi-LLM abstraction layer.

Defines the common interface all LLM providers must implement.
Providers are async-native and return empty strings on failure
(callers handle missing responses).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Provider-agnostic LLM interface for scoring and generation.

    All providers implement async generation with consistent error
    handling (log and return empty string on failure).
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        """Generate text from the model.

        Args:
            prompt: User prompt / main content to process
            system_prompt: System instruction / role definition
            temperature: Sampling temperature (0.0-1.0, default 0.3)
            max_tokens: Maximum output tokens (default 1000)

        Returns:
            Generated text, or empty string on failure.
            Errors are logged internally - callers handle empty responses.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging and debugging."""
        pass
