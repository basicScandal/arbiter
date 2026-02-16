"""Factory function for creating LLM providers by name.

Supports creating Gemini, Claude, and OpenAI providers with
consistent error handling.
"""

from __future__ import annotations

from src.providers.base import LLMProvider
from src.providers.claude_provider import ClaudeProvider
from src.providers.gemini_provider import GeminiProvider
from src.providers.openai_provider import OpenAIProvider


def create_provider(name: str, api_key: str) -> LLMProvider:
    """Create an LLM provider by name.

    Args:
        name: Provider name ("gemini", "claude", or "openai")
        api_key: API key for the provider

    Returns:
        Initialized LLMProvider instance

    Raises:
        ValueError: If provider name is not recognized
    """
    name_lower = name.lower().strip()

    if name_lower == "gemini":
        return GeminiProvider(api_key=api_key)
    elif name_lower == "claude":
        return ClaudeProvider(api_key=api_key)
    elif name_lower == "openai":
        return OpenAIProvider(api_key=api_key)
    else:
        raise ValueError(
            f"Unknown provider name: {name}. "
            f"Supported providers: gemini, claude, openai"
        )
