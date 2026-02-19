"""Shared utility functions used across multiple modules."""

from __future__ import annotations

import re


def sanitize_team_name(team_name: str) -> str:
    """Sanitize a team name for filesystem use.

    Replaces spaces with underscores, strips non-alphanumeric characters
    except underscores and hyphens, and lowercases the result.
    """
    name = team_name.replace(" ", "_")
    name = re.sub(r"[^a-zA-Z0-9_\-]", "", name)
    return name.lower()


def strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences from LLM responses.

    Many LLMs wrap JSON output in ```json ... ``` blocks even when told
    not to. This function removes those fences so the inner text can be
    parsed as raw JSON.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    return text
