"""Behavior lease compilation.

The compiler turns "we are about to judge team X" into an explicit, signed
contract: which effects are permitted, which claims those permissions rest on,
which monitors must be healthy, and when the whole thing expires.

Compilation is deterministic and evidence-driven -- it reads the live detector
pattern set, the track assignment, and the model identifiers actually in use,
so a lease always describes the system as configured rather than as documented.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid

from src.racp.models import (
    ActionKind,
    Assumption,
    BehaviorLease,
    Capabilities,
    LeaseState,
    MonitorSpec,
    RiskState,
)
from src.racp.signing import LeaseSigner

logger = logging.getLogger(__name__)

# A demo slot at NEBULA:FOG is 5 minutes plus scoring; 15 minutes of lease life
# covers a slot with headroom while still forcing renewal between teams.
DEFAULT_TTL_SECONDS = 900.0

# Assumption claims. Named constants because monitors invalidate them by name.
CLAIM_NO_INJECTION = "no_injection_in_demo_input"
CLAIM_SANITIZER_CLEAN = "sanitizer_output_is_clean"
CLAIM_OBSERVATION_PROVENANCE = "observations_describe_demo_not_slides"
CLAIM_POLICY_INTACT = "detection_policy_matches_preflighted_policy"
CLAIM_TEAM_IDENTITY = "task_is_for_the_named_team"
CLAIM_MONITORS_HEALTHY = "all_required_monitors_reporting"
CLAIM_BUDGET = "action_budget_not_exhausted"

# Reason recorded on a freshly compiled lease whose policy has not been tested
# yet. Distinguishing "never preflighted" from "preflighted and then diverged"
# matters: the first is a lease that is simply not ready, the second is a system
# running a policy nothing vouched for.
PREFLIGHT_PENDING = "preflight has not run for this lease"

# Claims a monitor can re-establish on its own, because they describe the
# *current* state and the monitor re-reads that state on every decision: a
# narrowed payload really is clean, the right team really is presenting again.
#
# The rest are sticky by design. An injection attempt is history and cannot be
# un-attempted, and policy integrity is established by preflight alone -- a
# policy that changed and changed back is still a policy nothing tested.
RENEWABLE_CLAIMS = frozenset(
    {
        CLAIM_SANITIZER_CLEAN,
        CLAIM_OBSERVATION_PROVENANCE,
        CLAIM_TEAM_IDENTITY,
        CLAIM_MONITORS_HEALTHY,
        CLAIM_BUDGET,
    }
)

# Events that force renewal before the next side effect.
INVALIDATION_EVENTS = [
    "injection_detected_high",
    "sanitizer_residue",
    "observation_provenance_conflict",
    "policy_set_changed",
    "team_changed",
    "monitor_unavailable",
    "budget_exhausted",
    "ttl_expired",
]


class TaskContext:
    """Everything the compiler needs to know about the task being authorized.

    Args:
        team_name: The presenting team this lease is scoped to.
        track: Assigned judging track.
        model: Identifier of the privileged judging model.
        harness: Identifier of the runtime wiring the lease was compiled under.
        policy_names: Names of the detection patterns currently loaded. Their
            hash is the policy provenance -- if a plugin adds or removes a
            pattern mid-event, the lease no longer matches the policy.
        requester: Who authorized this judging task.
        ttl_seconds: Lease lifetime.
    """

    def __init__(
        self,
        team_name: str,
        track: str = "",
        model: str = "",
        harness: str = "arbiter-capture-pipeline",
        policy_names: list[str] | None = None,
        requester: str = "operator",
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.team_name = team_name
        self.track = track
        self.model = model
        self.harness = harness
        self.policy_names = sorted(policy_names or [])
        self.requester = requester
        self.ttl_seconds = ttl_seconds

    def policy_hash(self) -> str:
        """Stable hash of the loaded detection policy set."""
        joined = "|".join(self.policy_names)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]

    def objective_hash(self) -> str:
        """Stable hash of the judging objective for this team and track."""
        objective = f"judge:{self.team_name}:{self.track}"
        return hashlib.sha256(objective.encode("utf-8")).hexdigest()[:16]


class LeaseCompiler:
    """Compiles and renews signed behavior leases.

    Args:
        signer: Signer used to seal every lease and renewal.
    """

    def __init__(self, signer: LeaseSigner | None = None) -> None:
        self._signer = signer or LeaseSigner()

    def compile(self, context: TaskContext, now: float | None = None) -> BehaviorLease:
        """Compile a fresh, signed lease for a judging task.

        The lease starts ACTIVE but is only *usable* once preflight has run --
        the gateway refuses effects for a lease whose policy-intact assumption
        has no preflight evidence behind it.
        """
        now = time.time() if now is None else now
        policy_hash = context.policy_hash()

        lease = BehaviorLease(
            lease_id=f"lease:{uuid.uuid4().hex[:16]}",
            revision=1,
            subject={
                "agent": "arbiter-judge",
                "model": context.model,
                "harness": context.harness,
            },
            task={
                "objective_hash": context.objective_hash(),
                "team_name": context.team_name,
                "track": context.track,
                "requester": context.requester,
            },
            capabilities=Capabilities(
                allow=[
                    ActionKind.PUBLISH_OBSERVATIONS.value,
                    ActionKind.SCORE_DEMO.value,
                    ActionKind.SPEAK_COMMENTARY.value,
                    ActionKind.PERSIST_SCORE.value,
                ],
                deny=[],
                budgets={
                    "max_injection_attempts": 12.0,
                    "max_observations": 500.0,
                },
            ),
            obligations=[
                "record every decision in the hash-chained log",
                "exclude tainted observations before the privileged LLM",
                "surface blocked effects to the operator dashboard",
            ],
            assumptions=[
                Assumption(
                    claim=CLAIM_POLICY_INTACT,
                    evidence=f"policy_hash={policy_hash} (preflight pending)",
                    holds=False,
                    invalidated_reason=PREFLIGHT_PENDING,
                ),
                Assumption(
                    claim=CLAIM_TEAM_IDENTITY,
                    evidence=f"demo_started team={context.team_name!r}",
                ),
                Assumption(
                    claim=CLAIM_NO_INJECTION,
                    evidence="no injection attempt observed yet",
                ),
                Assumption(
                    claim=CLAIM_SANITIZER_CLEAN,
                    evidence="sanitizer output not yet produced",
                ),
                Assumption(
                    claim=CLAIM_OBSERVATION_PROVENANCE,
                    evidence="no slide/observation conflict recorded",
                ),
                Assumption(
                    claim=CLAIM_MONITORS_HEALTHY,
                    evidence="monitor set healthy at issue time",
                ),
                Assumption(
                    claim=CLAIM_BUDGET,
                    evidence="no budget consumed",
                ),
            ],
            monitors=[
                MonitorSpec(id="injection_evidence", scope="demo"),
                MonitorSpec(id="sanitizer_residue", scope="action"),
                MonitorSpec(id="observation_provenance", scope="action"),
                MonitorSpec(id="policy_integrity", scope="action"),
                MonitorSpec(id="budget", scope="demo"),
            ],
            risk=RiskState(),
            invalidation_events=list(INVALIDATION_EVENTS),
            issued_at=now,
            expires_at=now + context.ttl_seconds,
            policy_provenance=[
                f"detector:{policy_hash}",
                f"patterns:{len(context.policy_names)}",
                f"track:{context.track or 'unassigned'}",
            ],
            state=LeaseState.ACTIVE,
        )
        return self._signer.sign(lease)

    def renew(
        self,
        lease: BehaviorLease,
        context: TaskContext,
        reason: str,
        restore_claims: list[str] | None = None,
        narrow: list[str] | None = None,
        now: float | None = None,
    ) -> BehaviorLease:
        """Issue the next revision of a lease with fresh evidence.

        Renewal is not a rubber stamp: only the claims listed in
        ``restore_claims`` are re-established, and only when the caller has
        supplied evidence for them. Everything else stays falsified, which is
        what keeps a renewal from silently widening authority.

        Args:
            lease: The lease being renewed.
            context: Current task context (re-read, not cached).
            reason: Why renewal was triggered.
            restore_claims: Claims the caller has fresh evidence for.
            narrow: Action kinds to move onto the deny list for this revision.
            now: Injectable clock.
        """
        now = time.time() if now is None else now
        renewed = lease.model_copy(deep=True)
        renewed.revision = lease.revision + 1
        renewed.issued_at = now
        renewed.expires_at = now + context.ttl_seconds
        renewed.state = LeaseState.ACTIVE

        restore = set(restore_claims or [])
        for assumption in renewed.assumptions:
            if assumption.claim in restore:
                assumption.holds = True
                assumption.invalidated_reason = ""
                assumption.established_at = now
                assumption.evidence = f"renewed r{renewed.revision}: {reason}"

        for kind in narrow or []:
            if kind not in renewed.capabilities.deny:
                renewed.capabilities.deny.append(kind)

        renewed.policy_provenance = renewed.policy_provenance + [
            f"renewal:r{renewed.revision}:{reason}"
        ]
        logger.info(
            "RACP lease %s renewed to r%d (%s)", renewed.lease_id, renewed.revision, reason
        )
        return self._signer.sign(renewed)

    def quarantine(self, lease: BehaviorLease, reason: str) -> BehaviorLease:
        """Move a lease to QUARANTINED so no effect can be authorized under it."""
        quarantined = lease.model_copy(deep=True)
        quarantined.state = LeaseState.QUARANTINED
        quarantined.policy_provenance = quarantined.policy_provenance + [
            f"quarantine:{reason}"
        ]
        return self._signer.sign(quarantined)

    def revoke(self, lease: BehaviorLease, reason: str) -> BehaviorLease:
        """Revoke a lease outright; enforced on the very next authorization."""
        revoked = lease.model_copy(deep=True)
        revoked.state = LeaseState.REVOKED
        revoked.policy_provenance = revoked.policy_provenance + [f"revoked:{reason}"]
        return self._signer.sign(revoked)
