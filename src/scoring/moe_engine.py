"""Mixture of Experts scoring engine running multiple LLM providers in parallel.

Each provider scores the same demo independently. Scores are aggregated
per-criterion with calibration and outlier detection. Python computes
weighted totals (SCORE-03 principle maintained).
"""

from __future__ import annotations

import asyncio
import logging
import time

from src.defense.models import SanitizedOutput
from src.providers.base import LLMProvider
from src.scoring.aggregator import ScoreAggregator
from src.scoring.engine import SCORING_SYSTEM_PROMPT, ScoringEngine
from src.scoring.models import CriterionScore, DemoScorecard, RubricCriterion, TrackCriteria
from src.scoring.rubric import GENERAL_CRITERIA, TRACK_CRITERIA

logger = logging.getLogger(__name__)


class MoEScoringEngine:
    """Multi-model scoring engine with ensemble aggregation.

    Runs multiple LLM providers in parallel on the same scoring prompt,
    then aggregates their per-criterion scores using calibrated weighted
    averaging with outlier detection.
    """

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("MoEScoringEngine requires at least one provider")
        self._providers = providers
        self._aggregator = ScoreAggregator()

    async def score(
        self,
        sanitized: SanitizedOutput,
        track: str,
        criteria: list[RubricCriterion] | None = None,
        track_criteria: dict[str, TrackCriteria] | None = None,
    ) -> DemoScorecard:
        """Score a demo using multiple models in parallel.

        All providers score the same rubric. Results are aggregated
        per-criterion. Python computes final weighted totals.
        """
        if criteria is None:
            criteria = GENERAL_CRITERIA
        if track_criteria is None:
            track_criteria = TRACK_CRITERIA

        prompt = ScoringEngine._build_prompt(sanitized, track, criteria, track_criteria)

        # Call all providers in parallel
        tasks = [
            provider.generate(
                prompt=prompt,
                system_prompt=SCORING_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=1000,
            )
            for provider in self._providers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Parse responses from each provider
        parsed: dict[str, DemoScorecard] = {}
        for provider, result in zip(self._providers, results):
            if isinstance(result, Exception):
                logger.warning("Provider %s raised exception: %s", provider.name, result)
                continue
            if not result:
                logger.warning("Provider %s returned empty response", provider.name)
                continue
            try:
                scorecard = ScoringEngine._parse_and_validate(
                    result, sanitized.team_name, track, criteria, track_criteria
                )
                parsed[provider.name] = scorecard
                logger.info(
                    "Provider %s scored team %s: %.1f",
                    provider.name, sanitized.team_name, scorecard.total_score,
                )
            except Exception:
                logger.warning(
                    "Failed to parse response from %s for team %s",
                    provider.name, sanitized.team_name,
                    exc_info=True,
                )

        # If no providers returned valid scores, use fallback
        if not parsed:
            logger.error(
                "All providers failed for team %s, returning fallback scorecard",
                sanitized.team_name,
            )
            return ScoringEngine._fallback_scorecard(
                sanitized.team_name, track, criteria
            )

        # If only one provider succeeded, return its scorecard directly
        if len(parsed) == 1:
            return next(iter(parsed.values()))

        # Aggregate per-criterion across providers
        return self._aggregate_scorecards(
            parsed, sanitized.team_name, track, criteria, track_criteria
        )

    def _aggregate_scorecards(
        self,
        parsed: dict[str, DemoScorecard],
        team_name: str,
        track: str,
        criteria: list[RubricCriterion],
        track_criteria: dict[str, TrackCriteria],
    ) -> DemoScorecard:
        """Aggregate per-criterion scores from multiple provider scorecards."""
        weight_map = {c.name: c.weight for c in criteria}

        # Collect per-criterion scores from each provider
        aggregated_criteria: list[CriterionScore] = []

        for criterion in criteria:
            provider_scores: dict[str, float] = {}
            provider_justifications: list[str] = []

            for prov_name, scorecard in parsed.items():
                for cs in scorecard.criteria:
                    if cs.name == criterion.name:
                        provider_scores[prov_name] = cs.score
                        if cs.justification:
                            provider_justifications.append(cs.justification)
                        break

            agg_score, metadata = self._aggregator.aggregate_criterion(provider_scores)

            # Use the longest justification (usually most detailed)
            best_justification = max(provider_justifications, key=len) if provider_justifications else ""
            if metadata.get("outliers"):
                best_justification += f" [MoE: {len(parsed)} models, outliers: {metadata['outliers']}]"

            aggregated_criteria.append(
                CriterionScore(
                    name=criterion.name,
                    score=max(0.0, min(10.0, agg_score)),
                    weight=weight_map.get(criterion.name, 0.0),
                    justification=best_justification,
                )
            )

        # Compute weighted total in Python
        total = sum(c.score * c.weight for c in aggregated_criteria)

        # Track bonus aggregation
        track_bonus: CriterionScore | None = None
        if track in track_criteria:
            bonus_scores: dict[str, float] = {}
            bonus_justifications: list[str] = []
            for prov_name, scorecard in parsed.items():
                if scorecard.track_bonus:
                    bonus_scores[prov_name] = scorecard.track_bonus.score
                    if scorecard.track_bonus.justification:
                        bonus_justifications.append(scorecard.track_bonus.justification)

            if bonus_scores:
                agg_bonus, _ = self._aggregator.aggregate_criterion(bonus_scores)
                bonus_weight = track_criteria[track].bonus_weight
                track_bonus = CriterionScore(
                    name=track_criteria[track].name,
                    score=max(0.0, min(10.0, agg_bonus)),
                    weight=bonus_weight,
                    justification=max(bonus_justifications, key=len) if bonus_justifications else "",
                )
                total += track_bonus.score * track_bonus.weight

        return DemoScorecard(
            team_name=team_name,
            track=track,
            criteria=aggregated_criteria,
            track_bonus=track_bonus,
            total_score=round(total, 1),
            scored_at=time.time(),
        )
