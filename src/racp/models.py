"""Data models for the Runtime Alignment Control Plane (RACP).

RACP treats the judge's authority to act as an *expiring, evidence-backed
lease* rather than a standing permission granted once at startup. Every
consequential effect in the judging pipeline -- publishing observations across
the privileged-LLM boundary, scoring a demo, speaking commentary -- is a
:class:`ProposedAction` that must be authorized against a live
:class:`BehaviorLease`.

Design notes:

* "Alignment" is never stored as a single boolean. Individual claims
  (:class:`Assumption`) carry their own evidence and expiry, because a stale
  slide-provenance check and an expired authorization window are different
  failures with different remedies.
* Risk is an *interpretable evidence score*, not a calibrated posterior. See
  :class:`RiskState`.
"""

from __future__ import annotations

import hashlib
import json
import time
from enum import Enum

from pydantic import BaseModel, Field

from src.capture.models import CaptureEvent

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DecisionOutcome(str, Enum):
    """Possible gateway rulings on a proposed action.

    Richer than allow/deny so the control plane can degrade gracefully at a
    live event instead of dropping a team's demo on the floor.
    """

    ALLOW = "allow"                       # execute within the current lease
    TRANSFORM = "transform"               # execute a narrowed/redacted variant
    SANDBOX = "sandbox"                   # execute without external effects
    REQUIRE_EVIDENCE = "require_evidence"  # missing observation/attestation
    REQUIRE_APPROVAL = "require_approval"  # pause for a human operator
    DENY = "deny"                         # reject, safe replanning permitted
    TERMINATE = "terminate"               # revoke the lease, stop the trajectory


class LeaseState(str, Enum):
    """Lifecycle state of a behavior lease."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    QUARANTINED = "quarantined"  # failed preflight; never activated


class ActionKind(str, Enum):
    """Consequential effects the gateway mediates.

    Anything not named here is unknown to the policy and therefore denied
    when enforcement is on -- unknown effects fail closed.
    """

    # Crossing the quarantined-LLM -> privileged-LLM boundary.
    PUBLISH_OBSERVATIONS = "publish_observations"
    # Handing sanitized text to the scoring ensemble.
    SCORE_DEMO = "score_demo"
    # Speaking generated commentary out loud to the room.
    SPEAK_COMMENTARY = "speak_commentary"
    # Writing a scorecard to durable storage.
    PERSIST_SCORE = "persist_score"


class Severity(str, Enum):
    """Monitor signal severity."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Lease components
# ---------------------------------------------------------------------------


class Assumption(BaseModel):
    """A single named claim the lease depends on, with its own evidence and TTL.

    An assumption that no longer holds invalidates the lease for the *next*
    side effect -- not retroactively, since prior effects already happened.
    """

    claim: str
    evidence: str = ""
    holds: bool = True
    established_at: float = Field(default_factory=time.time)
    expires_at: float = 0.0  # 0 means "expires with the lease"
    invalidated_reason: str = ""

    def is_live(self, now: float | None = None) -> bool:
        """Return True when the assumption still holds and has not expired."""
        now = time.time() if now is None else now
        if not self.holds:
            return False
        return self.expires_at == 0.0 or now < self.expires_at


class Capabilities(BaseModel):
    """What the agent may do under this lease, and how much of it."""

    allow: list[str] = []
    deny: list[str] = []
    budgets: dict[str, float] = {}

    def permits(self, action_kind: str) -> bool:
        """Default-deny capability check: explicit deny wins over allow."""
        if action_kind in self.deny:
            return False
        return action_kind in self.allow


class MonitorSpec(BaseModel):
    """A monitor the lease requires to be present and healthy."""

    id: str
    scope: str  # "action", "demo", or "session"
    threshold: float = 0.0
    required: bool = True


class RiskState(BaseModel):
    """Interpretable evidence score for the current trajectory.

    ``current`` is a bounded accumulation of monitor evidence weights, NOT a
    calibrated probability. Calling it a posterior would require empirical
    calibration against labelled incidents that this deployment does not have.
    """

    prior: float = 0.05
    current: float = 0.05
    calibration_version: str = "uncalibrated-v1"

    def bump(self, weight: float) -> None:
        """Accumulate evidence weight, clamped to [0, 1]."""
        self.current = max(0.0, min(1.0, self.current + weight))


class MonitorSignal(BaseModel):
    """One independent evidence signal about the current trajectory.

    Monitors are fallible security sensors, never authorities: no single
    signal may authorize a high-impact action on its own.
    """

    monitor_id: str
    triggered: bool
    severity: Severity = Severity.INFO
    detail: str = ""
    weight: float = 0.0
    invalidates: list[str] = []  # assumption claims this signal falsifies
    # Claims this monitor is responsible for, reported whether or not it fired.
    # A monitor reporting clean is what lets a renewable claim be re-established.
    covers: list[str] = []


# ---------------------------------------------------------------------------
# The lease itself
# ---------------------------------------------------------------------------


class BehaviorLease(BaseModel):
    """A task-scoped, expiring, signed authorization to act.

    Issued per demo after preflight passes; renewed (revision bumped) whenever
    a material assumption changes; revoked outright on critical evidence.
    """

    lease_id: str
    revision: int = 1
    subject: dict[str, str] = {}       # agent, model, harness
    task: dict[str, str] = {}          # objective_hash, team_name, track, requester
    capabilities: Capabilities = Capabilities()
    obligations: list[str] = []
    assumptions: list[Assumption] = []
    monitors: list[MonitorSpec] = []
    risk: RiskState = RiskState()
    invalidation_events: list[str] = []
    issued_at: float = Field(default_factory=time.time)
    expires_at: float = 0.0
    policy_provenance: list[str] = []
    state: LeaseState = LeaseState.ACTIVE
    signature: str = ""

    # -- assumption helpers -------------------------------------------------

    def assumption(self, claim: str) -> Assumption | None:
        """Return the named assumption, or None when the lease has no such claim."""
        for item in self.assumptions:
            if item.claim == claim:
                return item
        return None

    def stale_assumptions(self, now: float | None = None) -> list[Assumption]:
        """Return every assumption that no longer holds or has expired."""
        return [a for a in self.assumptions if not a.is_live(now)]

    def invalidate_assumption(self, claim: str, reason: str) -> bool:
        """Mark an assumption false. Returns True when a claim was found."""
        target = self.assumption(claim)
        if target is None:
            return False
        target.holds = False
        target.invalidated_reason = reason
        return True

    # -- lifecycle ----------------------------------------------------------

    def is_expired(self, now: float | None = None) -> bool:
        """Return True once the lease TTL has elapsed."""
        now = time.time() if now is None else now
        return self.expires_at != 0.0 and now >= self.expires_at

    def is_usable(self, now: float | None = None) -> bool:
        """Return True when the lease is active, unexpired, and fully assumed.

        This is deliberately strict: a lease with any stale assumption is not
        usable until it is renewed with fresh evidence.
        """
        if self.state is not LeaseState.ACTIVE:
            return False
        if self.is_expired(now):
            return False
        return not self.stale_assumptions(now)

    # -- signing ------------------------------------------------------------

    def signing_payload(self) -> bytes:
        """Canonical byte representation covered by the lease signature.

        Excludes the signature itself and the mutable risk score; every field
        that grants authority is covered.
        """
        data = self.model_dump(mode="json", exclude={"signature", "risk"})
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def fingerprint(self) -> str:
        """Short content hash, useful for logs and display."""
        return hashlib.sha256(self.signing_payload()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Actions and decisions
# ---------------------------------------------------------------------------


class ProposedAction(BaseModel):
    """A consequential effect awaiting authorization."""

    action_id: str
    kind: ActionKind
    team_name: str = ""
    summary: str = ""
    irreversible: bool = False
    payload_digest: str = ""
    timestamp: float = Field(default_factory=time.time)

    @staticmethod
    def digest(payload: object) -> str:
        """Stable digest of an action payload for the audit trail.

        The payload itself is never written to the log -- it may contain the
        attacker-controlled text we are defending against.
        """
        blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:32]


class Decision(BaseModel):
    """The gateway's ruling on one proposed action."""

    action_id: str
    kind: ActionKind
    team_name: str = ""
    outcome: DecisionOutcome
    reason: str = ""
    lease_id: str = ""
    lease_revision: int = 0
    signals: list[MonitorSignal] = []
    risk: float = 0.0
    enforced: bool = True  # False when the gateway ran in shadow mode
    # In shadow mode the effective outcome is ALLOW and this records the
    # outcome enforcement *would* have produced, so a rollout can be measured
    # before it can block anything.
    shadow_outcome: DecisionOutcome | None = None
    latency_us: float = 0.0
    timestamp: float = Field(default_factory=time.time)

    @property
    def permits_effect(self) -> bool:
        """True when the action may proceed with its full external effect."""
        return self.outcome in (DecisionOutcome.ALLOW, DecisionOutcome.TRANSFORM)

    @property
    def blocked(self) -> bool:
        """True when the action must not produce its intended effect."""
        return not self.permits_effect

    @property
    def should_surface(self) -> bool:
        """True when the operator should be told about this ruling.

        Covers refusals, narrowed payloads, and shadow-mode rulings that let the
        effect through -- a rollout needs to see what enforcement *would* have
        stopped, not only what it did stop.
        """
        return (
            self.blocked
            or self.outcome is DecisionOutcome.TRANSFORM
            or self.shadow_outcome is not None
        )


class PreflightProbe(BaseModel):
    """A task-shaped adversarial probe run before a lease is activated."""

    probe_id: str
    text: str
    vector: str  # "visual", "verbal", or "observation"
    must_detect: bool = True
    rationale: str = ""


class PreflightReport(BaseModel):
    """Outcome of the preflight evaluation for one lease."""

    passed: bool
    probes_run: int = 0
    probes_missed: list[str] = []
    mutation_score: float = 0.0
    mutations_run: int = 0
    mutations_caught: int = 0
    detail: str = ""
    duration_us: float = 0.0


# ---------------------------------------------------------------------------
# Event-bus events
# ---------------------------------------------------------------------------


class LeaseIssued(CaptureEvent):
    """Emitted when a lease is issued or renewed for a demo."""

    event_type: str = "racp_lease_issued"
    lease: BehaviorLease
    renewal: bool = False
    reason: str = ""


class LeaseInvalidated(CaptureEvent):
    """Emitted when evidence falsifies one or more lease assumptions."""

    event_type: str = "racp_lease_invalidated"
    lease_id: str
    team_name: str = ""
    claims: list[str] = []
    reason: str = ""


class LeaseQuarantined(CaptureEvent):
    """Emitted when preflight rejects a compiled policy."""

    event_type: str = "racp_lease_quarantined"
    lease_id: str
    team_name: str = ""
    report: PreflightReport


class ActionBlocked(CaptureEvent):
    """Emitted when the gateway refuses or downgrades a consequential action."""

    event_type: str = "racp_action_blocked"
    decision: Decision
