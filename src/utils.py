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


class TeamNameCollisionError(ValueError):
    """Raised when two distinct team names produce the same storage slug."""


class TeamSlugRegistry:
    """Maps sanitized slugs to canonical display names to detect collisions."""

    def __init__(self) -> None:
        self._registry: dict[str, str] = {}  # slug -> canonical display name

    def resolve(self, display_name: str) -> str:
        """Return the slug for a display name, registering it or checking for collision."""
        slug = sanitize_team_name(display_name)
        if not slug:
            raise ValueError("Team name produces an empty slug")

        existing = self._registry.get(slug)
        if existing is None:
            self._registry[slug] = display_name
            return slug

        if existing != display_name:
            raise TeamNameCollisionError(
                f"Team name {display_name!r} collides with existing team {existing!r} "
                f"(both produce slug {slug!r})"
            )
        return slug

    def clear(self) -> None:
        """Clear the registry (for testing or between events)."""
        self._registry.clear()


# Module-level singleton
_slug_registry = TeamSlugRegistry()


def resolve_team_slug(display_name: str) -> str:
    """Resolve a display name to a slug, checking for collisions."""
    return _slug_registry.resolve(display_name)


def clear_team_registry() -> None:
    """Clear the team slug registry."""
    _slug_registry.clear()


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
