"""Multi-provider LLM abstraction layer for Arbiter.

Provides a unified interface for Gemini, Claude, and OpenAI models
to support mixture-of-experts scoring with different models as
specialized judges.

Example usage:
    from src.providers import create_provider, LLMProvider

    provider = create_provider("gemini", api_key="...")
    result = await provider.generate(
        prompt="Score this demo",
        system_prompt="You are a hackathon judge",
        temperature=0.3,
        max_tokens=1000
    )
"""

from __future__ import annotations

from src.providers.base import LLMProvider
from src.providers.claude_provider import ClaudeProvider
from src.providers.factory import create_provider
from src.providers.gemini_provider import GeminiProvider
from src.providers.openai_provider import OpenAIProvider

__all__ = [
    "LLMProvider",
    "GeminiProvider",
    "ClaudeProvider",
    "OpenAIProvider",
    "create_provider",
]
