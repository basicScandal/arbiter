"""Canned LLM response provider for rehearsal mode.

Returns deterministic responses matching Arbiter's expected formats without
making any real API calls. Used by RehearsalPipeline to exercise the full
pipeline chain with predictable outputs.
"""

from __future__ import annotations

import json
import logging

from src.providers.base import LLMProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canned responses
# ---------------------------------------------------------------------------

_SCORING_RESPONSE = json.dumps(
    {
        "criteria": [
            {
                "name": "Technical Execution",
                "score": 8.5,
                "justification": "Strong implementation of the network reconnaissance module with clean error handling and modular architecture.",
            },
            {
                "name": "Innovation",
                "score": 7.0,
                "justification": "Novel approach to automated vulnerability correlation using graph-based analysis.",
            },
            {
                "name": "Demo Quality",
                "score": 6.5,
                "justification": "Live demo worked but the explanation was slightly rushed during the architecture walkthrough.",
            },
        ],
        "track_bonus": {
            "name": "Originality Factor",
            "score": 7.5,
            "justification": "Creative integration of LLM reasoning with traditional security tooling.",
        },
    },
    indent=2,
)

_COMMENTARY_RESPONSE = (
    "Well, well, well -- what do we have here? A team that actually "
    "knows what they're doing. The network recon module is impressively "
    "clean, though I've seen tidier codebases in my sleep. "
    "Still, I'll give credit where it's due -- that graph-based vuln "
    "correlation is a genuinely clever touch."
)

_DELIBERATION_RESPONSE = json.dumps(
    {
        "rankings": [
            {
                "rank": 1,
                "team_name": "RehearsalTeam",
                "total_score": 7.4,
                "track": "ROGUE::AGENT",
                "reasoning": "Strong technical execution and innovative approach set this team apart.",
            }
        ],
        "overall_narrative": (
            "A solid showing from RehearsalTeam. The combination of "
            "technical skill and creative thinking made for a compelling "
            "demo, even if the presentation could use a bit more polish."
        ),
    },
    indent=2,
)

_QA_RESPONSE = (
    "Here's a question that should make them squirm: How does your "
    "graph-based correlation handle adversarial nodes that deliberately "
    "inject false vulnerability data into the analysis pipeline?"
)

_DEFAULT_RESPONSE = "[ReplayProvider] No specific canned response matched this prompt."


class ReplayProvider(LLMProvider):
    """LLMProvider that returns canned responses for rehearsal mode.

    Inspects prompt and system_prompt keywords to determine which canned
    response to return. No real API calls are made. Useful for testing
    the full pipeline chain without external dependencies.
    """

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self._custom_responses = responses or {}
        self._call_count: int = 0

    @property
    def name(self) -> str:
        """Provider name for logging and debugging."""
        return "replay"

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        """Return a canned response based on prompt/system_prompt keywords.

        Args:
            prompt: User prompt content.
            system_prompt: System instruction / role definition.
            temperature: Ignored (deterministic responses).
            max_tokens: Ignored (deterministic responses).

        Returns:
            A canned response string matching the expected format.
        """
        self._call_count += 1

        sp_lower = system_prompt.lower()
        p_lower = prompt.lower()

        # Check custom responses first
        for keyword, response in self._custom_responses.items():
            if keyword.lower() in sp_lower or keyword.lower() in p_lower:
                logger.debug("ReplayProvider matched custom keyword: %s", keyword)
                return response

        # Scoring response
        if "scoring" in sp_lower:
            logger.debug("ReplayProvider returning canned scoring response")
            return _SCORING_RESPONSE

        # Commentary response (Arbiter persona)
        if "arbiter" in sp_lower or "persona" in sp_lower:
            logger.debug("ReplayProvider returning canned commentary response")
            return _COMMENTARY_RESPONSE

        # Deliberation response
        if "deliberat" in sp_lower:
            logger.debug("ReplayProvider returning canned deliberation response")
            return _DELIBERATION_RESPONSE

        # Q&A response
        if "question" in p_lower or "q&a" in p_lower:
            logger.debug("ReplayProvider returning canned Q&A response")
            return _QA_RESPONSE

        # Default fallback
        logger.debug("ReplayProvider returning default response (call #%d)", self._call_count)
        return _DEFAULT_RESPONSE
