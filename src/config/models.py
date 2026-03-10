"""LLM model identifiers used across the codebase.

Centralizes model strings so upgrades are a one-line change.
Configurable via environment variables with sensible defaults.
"""

from __future__ import annotations

import os

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
