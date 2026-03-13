"""LLM model identifiers used across the codebase.

Centralizes model strings so upgrades are a one-line change.
Configurable via environment variables with sensible defaults.
"""

from __future__ import annotations

import os

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
CLAUDE_HAIKU_MODEL = os.environ.get("CLAUDE_HAIKU_MODEL", "claude-haiku-4-5-20251001")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_FLASH_MODEL = os.environ.get("GEMINI_FLASH_MODEL", "gemini-2.0-flash")
GEMINI_LIVE_MODEL = os.environ.get("GEMINI_LIVE_MODEL", "gemini-live-2.5-flash-native-audio")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
