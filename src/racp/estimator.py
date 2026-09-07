"""Trajectory state estimation from monitor evidence.

Turns a list of :class:`MonitorSignal` into two things the gateway needs: which
lease assumptions are now falsified, and how much accumulated evidence of
compromise the trajectory carries.

The score is an **interpretable evidence total**, not a calibrated posterior.
Weights are stated in the monitors and summed here; nothing about that produces
a probability, and the class deliberately does not pretend otherwise. Promoting
it to a Bayesian estimate would require labelled incidents and negative cases
from real events, which is exactly the calibration this deployment lacks.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from src.racp.models import BehaviorLease, MonitorSignal, Severity

logger = logging.getLogger(__name__)

# Evidence at or above this total is treated as a compromised trajectory.
COMPROMISE_THRESHOLD = 0.5
# Evidence at or above this total warrants human adjudication.
ELEVATED_THRESHOLD = 0.25


class TrajectoryState(BaseModel):
    """Estimator output for one authorization decision."""

    risk: float = 0.0
    invalidated_claims: list[str] = []
    critical: bool = False
    elevated: bool = False
    rationale: list[str] = []

    @property
    def compromised(self) -> bool:
        """True when evidence indicates the trajectory can no longer be trusted."""
        return self.critical or self.risk >= COMPROMISE_THRESHOLD


class StateEstimator:
    """Accumulates monitor evidence into a trajectory state.

    Args:
        compromise_threshold: Evidence total treated as compromise.
        elevated_threshold: Evidence total warranting human review.
    """

    def __init__(
        self,
        compromise_threshold: float = COMPROMISE_THRESHOLD,
        elevated_threshold: float = ELEVATED_THRESHOLD,
    ) -> None:
        self._compromise = compromise_threshold
        self._elevated = elevated_threshold

    def assess(
        self, lease: BehaviorLease, signals: list[MonitorSignal]
    ) -> TrajectoryState:
        """Fold signals into a trajectory state without mutating the lease."""
        risk = lease.risk.prior
        claims: list[str] = []
        rationale: list[str] = []
        critical = False

        for signal in signals:
            if not signal.triggered:
                continue
            risk += signal.weight
            rationale.append(f"{signal.monitor_id}: {signal.detail}")
            for claim in signal.invalidates:
                if claim not in claims:
                    claims.append(claim)
            if signal.severity is Severity.CRITICAL:
                critical = True

        risk = max(0.0, min(1.0, risk))
        return TrajectoryState(
            risk=risk,
            invalidated_claims=claims,
            critical=critical,
            elevated=risk >= self._elevated,
            rationale=rationale,
        )
