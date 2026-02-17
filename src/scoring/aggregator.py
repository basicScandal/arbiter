"""Score aggregation for multi-model MoE scoring.

Combines scores from multiple LLM providers using calibrated
weighted averaging with outlier detection.
"""

from __future__ import annotations

import logging
import statistics

logger = logging.getLogger(__name__)

# Per-model calibration defaults.
# temperature: Higher = flatten extreme scores toward center.
# bias: Additive correction (positive = model scores low, negative = scores high).
DEFAULT_CALIBRATION: dict[str, dict[str, float]] = {
    "gemini": {"temperature": 1.1, "bias": -0.2},
    "claude": {"temperature": 1.2, "bias": 0.0},
    "openai": {"temperature": 1.5, "bias": 0.3},
    "groq": {"temperature": 1.0, "bias": 0.0},  # Neutral defaults — needs empirical calibration
}

OUTLIER_THRESHOLD = 2.0  # Points from median to flag as outlier
OUTLIER_WEIGHT_REDUCTION = 0.5  # Outlier weight multiplied by this


class ScoreAggregator:
    """Aggregates per-criterion scores from multiple models."""

    def __init__(self, calibration: dict[str, dict[str, float]] | None = None) -> None:
        self._calibration = calibration or DEFAULT_CALIBRATION

    def calibrate_score(self, score: float, provider_name: str) -> float:
        """Apply temperature scaling and bias correction to a raw score.

        Temperature scaling: (score - 5.0) / T + 5.0 (centers around midpoint)
        Then add bias correction.
        Clamp result to 0.0-10.0.
        """
        # Extract base provider name (e.g., "gemini" from "gemini:gemini-2.5-flash")
        base_name = provider_name.split(":")[0] if ":" in provider_name else provider_name
        cal = self._calibration.get(base_name, {"temperature": 1.0, "bias": 0.0})

        t = cal["temperature"]
        bias = cal["bias"]

        calibrated = (score - 5.0) / t + 5.0 + bias
        return max(0.0, min(10.0, calibrated))

    def aggregate_criterion(
        self, scores: dict[str, float],
    ) -> tuple[float, dict]:
        """Aggregate scores for one criterion from multiple models.

        Args:
            scores: Mapping of provider_name -> raw score for this criterion

        Returns:
            (aggregated_score, metadata) where metadata includes outlier flags
        """
        if not scores:
            return 5.0, {"error": "no_scores"}

        if len(scores) == 1:
            name, raw = next(iter(scores.items()))
            calibrated = self.calibrate_score(raw, name)
            return round(calibrated, 1), {"single_model": name}

        # Calibrate all scores
        calibrated: dict[str, float] = {
            name: self.calibrate_score(raw, name)
            for name, raw in scores.items()
        }

        # Compute median for outlier detection
        values = list(calibrated.values())
        median = statistics.median(values)

        # Build weights: default 1.0, reduce for outliers
        weights: dict[str, float] = {}
        outliers: list[str] = []
        for name, cal_score in calibrated.items():
            if abs(cal_score - median) > OUTLIER_THRESHOLD:
                weights[name] = OUTLIER_WEIGHT_REDUCTION
                outliers.append(name)
            else:
                weights[name] = 1.0

        # Weighted average (all-outlier guard: if every model deviates from
        # median by >2 points, just use the median rather than a skewed average)
        total_weight = sum(weights.values())
        if len(outliers) == len(calibrated):
            return round(median, 1), {"all_outliers": True}

        weighted_sum = sum(calibrated[name] * weights[name] for name in calibrated)
        final = weighted_sum / total_weight

        metadata = {
            "individual_scores": {name: round(s, 1) for name, s in calibrated.items()},
            "raw_scores": dict(scores),
            "outliers": outliers,
            "median": round(median, 1),
            "confidence": round(1.0 - (statistics.stdev(values) / 10.0 if len(values) > 1 else 0.0), 2),
        }

        return round(final, 1), metadata
