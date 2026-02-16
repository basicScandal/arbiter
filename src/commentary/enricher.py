"""Commentary enrichment via secondary LLM model.

Takes raw Gemini commentary and refines it through a second model
(Claude or OpenAI) for sharper wit and deeper technical insights.
Operates with a strict timeout -- falls back to original if enrichment
is too slow or fails.
"""

from __future__ import annotations

import asyncio
import logging

from src.commentary.models import Commentary
from src.providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Strict timeout -- prefer fast fallback to original commentary over
# waiting for retries. The provider's internal retry budget will be
# cut short by this timeout, which is intentional: enrichment is a
# nice-to-have, not worth adding latency to commentary delivery.
ENRICHMENT_TIMEOUT = 8.0  # seconds -- original used if exceeded

ENRICHMENT_PROMPT = """\
You are a comedy writer and technical editor for Arbiter, an AI judge \
at a security hackathon. Your job is to take draft commentary and \
make it LAND HARDER.

RULES:
1. Sharpen witty observations -- make the punchlines crisper
2. Add one specific technical insight the draft may have missed
3. Maintain Simon Cowell-meets-hacker tone (adversarial but never \
   targeting the person)
4. Keep it to 3-5 sentences total -- every word must earn its place
5. Maintain the same factual content -- do NOT invent observations
6. Output plain text only -- no markdown, no bullet points

Draft commentary:
{draft}

Demo observations (for reference):
{observations}

Output the refined commentary as plain text. One continuous paragraph.\
"""


class CommentaryEnricher:
    """Enriches raw commentary through a secondary LLM for quality boost.

    Operates with a strict timeout. If the enrichment model fails or
    is too slow, the original Gemini commentary is used unchanged.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def enrich(
        self,
        commentary: Commentary,
        observations: list[str],
    ) -> Commentary:
        """Enrich commentary text via secondary model.

        Args:
            commentary: Raw Commentary from Gemini CommentaryGenerator
            observations: Sanitized observations from the demo

        Returns:
            Enriched Commentary with updated text and sentences,
            or original Commentary if enrichment fails/times out.
        """
        if not commentary.text or commentary.text == "Technical difficulties. Even Arbiter needs a moment.":
            return commentary

        prompt = ENRICHMENT_PROMPT.format(
            draft=commentary.text,
            observations="\n".join(f"- {obs}" for obs in observations[:5]),
        )

        try:
            enriched_text = await asyncio.wait_for(
                self._provider.generate(
                    prompt=prompt,
                    system_prompt="You refine AI judge commentary to be sharper and funnier.",
                    temperature=0.7,
                    max_tokens=400,
                ),
                timeout=ENRICHMENT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Enrichment timed out after %.1fs for team %s, using original",
                ENRICHMENT_TIMEOUT,
                commentary.team_name,
            )
            return commentary
        except Exception:
            logger.warning(
                "Enrichment failed for team %s, using original",
                commentary.team_name,
                exc_info=True,
            )
            return commentary

        if not enriched_text.strip():
            logger.warning("Enrichment returned empty, using original for team %s", commentary.team_name)
            return commentary

        # Rebuild Commentary with enriched text
        # Reuse the sentence splitting and emotion mapping from CommentaryGenerator
        from src.commentary.generator import CommentaryGenerator

        enriched_text = enriched_text.strip()
        sentences = CommentaryGenerator._split_sentences(enriched_text)
        emotion_map = CommentaryGenerator._build_emotion_map(sentences)

        logger.info(
            "Commentary enriched for team %s (%d→%d chars)",
            commentary.team_name,
            len(commentary.text),
            len(enriched_text),
        )

        return Commentary(
            team_name=commentary.team_name,
            text=enriched_text,
            sentences=sentences,
            emotion_map=emotion_map,
            generated_at=commentary.generated_at,
        )
