"""The action enforcement gateway.

Every consequential effect in the judging pipeline passes through
:meth:`ActionGateway.authorize` before it happens. The gateway holds the live
lease for each team, runs the monitor ensemble against observed evidence,
renews or revokes the lease just in time, records the ruling in the
hash-chained log, and returns a :class:`Decision`.

Two rules define its posture:

* **Fail closed for effects.** Every action kind the gateway mediates produces
  an external effect -- text crossing the privileged-LLM boundary, a score
  written down, a voice in the room. A missing lease, an unverifiable
  signature, an unknown action kind, or a monitor that cannot run all end in
  refusal, never in a silent pass.
* **Renew before the effect, not after.** When evidence falsifies an
  assumption, the lease is re-issued at the same action boundary that
  surfaced it. There is no window in which a stale lease authorizes work.

Shadow mode (``enforce=False``) computes and logs the identical decision but
returns ALLOW, so a deployment can measure block rates before granting the
gateway the authority to stop a live demo.
"""

from __future__ import annotations

import logging
import time
import uuid

from src.racp.audit import DecisionLog
from src.racp.compiler import (
    CLAIM_MONITORS_HEALTHY,
    CLAIM_POLICY_INTACT,
    CLAIM_SANITIZER_CLEAN,
    CLAIM_TEAM_IDENTITY,
    PREFLIGHT_PENDING,
    RENEWABLE_CLAIMS,
    LeaseCompiler,
    TaskContext,
)
from src.racp.estimator import StateEstimator, TrajectoryState
from src.racp.models import (
    ActionKind,
    BehaviorLease,
    Decision,
    DecisionOutcome,
    LeaseState,
    MonitorSignal,
    PreflightReport,
    ProposedAction,
)
from src.racp.monitors import Evidence, MonitorEnsemble
from src.racp.signing import LeaseSigner

logger = logging.getLogger(__name__)

# Actions whose effect cannot be taken back once it happens: spoken audio in a
# room, a published ranking, a persisted scorecard. These escalate to human
# approval where a reversible action would merely be denied and replanned.
IRREVERSIBLE_KINDS = frozenset(
    {
        ActionKind.SPEAK_COMMENTARY,
        ActionKind.PERSIST_SCORE,
    }
)


class ActionGateway:
    """Authorizes consequential actions against live behavior leases.

    Args:
        compiler: Lease compiler used for issuance, renewal, and revocation.
        signer: Signer used to verify leases on every authorization. Must be
            the same signer the compiler seals leases with.
        log: Hash-chained decision log.
        monitors: Monitor ensemble producing independent evidence.
        estimator: Folds monitor signals into a trajectory state.
        enforce: When False the gateway runs in shadow mode -- decisions are
            computed and logged but never block.
    """

    def __init__(
        self,
        compiler: LeaseCompiler | None = None,
        signer: LeaseSigner | None = None,
        log: DecisionLog | None = None,
        monitors: MonitorEnsemble | None = None,
        estimator: StateEstimator | None = None,
        enforce: bool = True,
    ) -> None:
        self._signer = LeaseSigner() if signer is None else signer
        self._compiler = LeaseCompiler(self._signer) if compiler is None else compiler
        # `is None` rather than `or`: an empty DecisionLog is falsy (it defines
        # __len__), and `log or DecisionLog()` would silently swap a configured,
        # disk-backed audit chain for an in-memory one.
        self._log = DecisionLog() if log is None else log
        self._monitors = MonitorEnsemble() if monitors is None else monitors
        self._estimator = StateEstimator() if estimator is None else estimator
        self._enforce = enforce
        self._leases: dict[str, BehaviorLease] = {}
        self._contexts: dict[str, TaskContext] = {}

    # -- lease lifecycle ----------------------------------------------------

    @property
    def log(self) -> DecisionLog:
        """The hash-chained decision log."""
        return self._log

    @property
    def enforcing(self) -> bool:
        """True when decisions actually block; False in shadow mode."""
        return self._enforce

    def lease_for(self, team_name: str) -> BehaviorLease | None:
        """Return the live lease for a team, if one has been issued."""
        return self._leases.get(team_name)

    def issue(
        self, context: TaskContext, report: PreflightReport | None = None
    ) -> BehaviorLease:
        """Compile a lease for a task and activate it if preflight passed.

        A lease is issued in every case -- a quarantined lease is the record
        that judging was attempted under a policy that could not be vouched
        for. Only a passing preflight establishes the policy-intact assumption,
        and without that assumption no effect is authorized.
        """
        lease = self._compiler.compile(context)

        if report is not None and report.passed:
            lease = self._compiler.renew(
                lease,
                context,
                reason=f"preflight passed ({report.detail})",
                restore_claims=[CLAIM_POLICY_INTACT],
            )
        elif report is not None:
            lease = self._compiler.quarantine(
                lease, reason=f"preflight failed ({report.detail})"
            )
            logger.error(
                "RACP: lease %s QUARANTINED for team %s — %s",
                lease.lease_id,
                context.team_name,
                report.detail,
            )

        self._leases[context.team_name] = lease
        self._contexts[context.team_name] = context
        return lease

    def invalidate(self, team_name: str, claims: list[str], reason: str) -> BehaviorLease | None:
        """Falsify named assumptions on a team's lease.

        Called from event handlers (a high-confidence injection detection, an
        operator override) so that evidence arriving between actions is already
        reflected when the next action is proposed.
        """
        lease = self._leases.get(team_name)
        if lease is None:
            return None
        updated = lease.model_copy(deep=True)
        changed = [c for c in claims if updated.invalidate_assumption(c, reason)]
        if not changed:
            return lease
        self._leases[team_name] = self._signer.sign(updated)
        logger.info(
            "RACP: lease %s assumptions invalidated (%s) — %s",
            lease.lease_id,
            ", ".join(changed),
            reason,
        )
        return self._leases[team_name]

    def revoke(self, team_name: str, reason: str) -> BehaviorLease | None:
        """Revoke a team's lease; enforced on the very next authorization."""
        lease = self._leases.get(team_name)
        if lease is None:
            return None
        self._leases[team_name] = self._compiler.revoke(lease, reason)
        logger.warning("RACP: lease revoked for %s — %s", team_name, reason)
        return self._leases[team_name]

    # -- authorization ------------------------------------------------------

    def authorize(self, action: ProposedAction, evidence: Evidence) -> Decision:
        """Rule on a proposed action and record the ruling.

        Args:
            action: The effect the pipeline wants to produce.
            evidence: Observed state gathered at the enforcement point.

        Returns:
            A :class:`Decision`. Callers must honour ``decision.permits_effect``
            and treat TRANSFORM as "proceed, but with the narrowed payload the
            reason describes".
        """
        started = time.perf_counter()
        lease = self._leases.get(action.team_name)

        outcome, reason, signals, state = self._rule(action, evidence, lease)

        decision = Decision(
            action_id=action.action_id,
            kind=action.kind,
            team_name=action.team_name,
            outcome=outcome,
            reason=reason,
            lease_id=lease.lease_id if lease else "",
            lease_revision=lease.revision if lease else 0,
            signals=signals,
            risk=state.risk if state else 0.0,
            enforced=self._enforce,
            latency_us=(time.perf_counter() - started) * 1_000_000,
        )

        if not self._enforce and decision.blocked:
            decision.shadow_outcome = outcome
            decision.outcome = DecisionOutcome.ALLOW
            decision.reason = f"shadow mode: would have been {outcome.value} — {reason}"

        self._log.append(decision)

        if decision.blocked:
            logger.warning(
                "RACP %s %s for %s: %s",
                decision.outcome.value.upper(),
                action.kind.value,
                action.team_name or "<unknown team>",
                reason,
            )
        return decision

    # -- internals ----------------------------------------------------------

    def _rule(
        self,
        action: ProposedAction,
        evidence: Evidence,
        lease: BehaviorLease | None,
    ) -> tuple[DecisionOutcome, str, list[MonitorSignal], TrajectoryState | None]:
        """Compute the outcome for an action.

        Not side-effect free: just-in-time enforcement means this reconciles the
        lease's assumptions with current evidence, renews it on TTL expiry, and
        revokes it on policy divergence, all before the effect is ruled on.
        """
        # --- structural checks: no evidence gathering needed to refuse -----
        if lease is None:
            return (
                DecisionOutcome.DENY,
                "no behavior lease issued for this team; effects fail closed",
                [],
                None,
            )
        if not self._signer.verify(lease):
            return (
                DecisionOutcome.TERMINATE,
                "lease signature does not verify — lease may have been tampered with",
                [],
                None,
            )
        if lease.state is LeaseState.QUARANTINED:
            return (
                DecisionOutcome.DENY,
                "lease quarantined: the detection policy failed preflight",
                [],
                None,
            )
        if lease.state is LeaseState.REVOKED:
            return (DecisionOutcome.DENY, "lease revoked", [], None)
        if not lease.capabilities.permits(action.kind.value):
            return (
                DecisionOutcome.DENY,
                f"action {action.kind.value} is not in the lease capability set",
                [],
                None,
            )

        # --- evidence gathering --------------------------------------------
        signals = self._monitors.evaluate(lease, evidence)
        state = self._estimator.assess(lease, signals)

        # Fold the current reading into the lease before deciding, so the
        # decision is made against current state rather than issue-time state.
        lease = self._reconcile(action.team_name, lease, signals, state)

        # --- TTL: renew just in time, before the effect ---------------------
        if lease.is_expired():
            renewed = self._renew_for_ttl(action.team_name, lease, state)
            if renewed is None:
                return (
                    DecisionOutcome.DENY,
                    "lease expired and cannot be renewed under current evidence",
                    signals,
                    state,
                )
            lease = renewed

        # --- rulings driven by which claim failed ---------------------------
        stale = {a.claim for a in lease.stale_assumptions()}

        if CLAIM_POLICY_INTACT in stale:
            policy_claim = lease.assumption(CLAIM_POLICY_INTACT)
            if policy_claim is not None and policy_claim.invalidated_reason == PREFLIGHT_PENDING:
                # Never tested rather than tested-and-diverged: the lease is not
                # ready, but nothing suggests the running system is unsound.
                return (
                    DecisionOutcome.DENY,
                    "the detection policy has not been preflighted for this demo",
                    signals,
                    state,
                )
            # The policy in force is not the policy that was tested. Nothing
            # downstream of an untested policy can be trusted, so stop rather
            # than narrow.
            self.revoke(action.team_name, "detection policy diverged from preflight")
            return (
                DecisionOutcome.TERMINATE,
                "detection policy no longer matches the preflighted policy",
                signals,
                state,
            )

        if CLAIM_TEAM_IDENTITY in stale:
            return (
                DecisionOutcome.DENY,
                "action does not belong to the team this lease covers (cross-demo bleed)",
                signals,
                state,
            )

        if CLAIM_MONITORS_HEALTHY in stale:
            return (
                DecisionOutcome.REQUIRE_EVIDENCE,
                "a required monitor is unavailable; effect withheld pending coverage",
                signals,
                state,
            )

        if CLAIM_SANITIZER_CLEAN in stale:
            # Injection text survived sanitization and is one step from the
            # privileged judge. Boundary-crossing gets a narrowed payload;
            # anything further downstream stops outright.
            if action.kind is ActionKind.PUBLISH_OBSERVATIONS:
                return (
                    DecisionOutcome.TRANSFORM,
                    "injection residue found in sanitized output; "
                    "publish with residue removed and mark the demo degraded",
                    signals,
                    state,
                )
            return (
                DecisionOutcome.DENY,
                "injection residue detected downstream of the sanitizer",
                signals,
                state,
            )

        # --- rulings driven by accumulated evidence -------------------------
        if state.compromised:
            if action.kind in IRREVERSIBLE_KINDS or action.irreversible:
                return (
                    DecisionOutcome.REQUIRE_APPROVAL,
                    f"evidence score {state.risk:.2f} on an irreversible action; "
                    "operator adjudication required",
                    signals,
                    state,
                )
            return (
                DecisionOutcome.DENY,
                f"evidence score {state.risk:.2f} exceeds the compromise threshold",
                signals,
                state,
            )

        if state.elevated:
            # Injection was attempted and the defense held. This is the normal,
            # expected case at a security hackathon: the demo is still judged,
            # the lease carries the falsified claim into the next decision.
            return (
                DecisionOutcome.ALLOW,
                f"elevated evidence ({state.risk:.2f}) within lease tolerance",
                signals,
                state,
            )

        return (DecisionOutcome.ALLOW, "within lease", signals, state)

    def _reconcile(
        self,
        team_name: str,
        lease: BehaviorLease,
        signals: list[MonitorSignal],
        state: TrajectoryState,
    ) -> BehaviorLease:
        """Bring the lease's assumptions in line with what the monitors just saw.

        Falsified claims are recorded. Renewable claims whose monitor now reads
        clean are re-established with that fresh reading as their evidence --
        which is what lets a demo continue after a narrowed payload fixed the
        problem, without ever letting a sticky claim (an injection was
        attempted; the policy diverged) be laundered by a later quiet reading.
        """
        updated = lease.model_copy(deep=True)
        changed = False

        for signal in signals:
            if signal.triggered:
                for claim in signal.invalidates:
                    if updated.invalidate_assumption(
                        claim, f"{signal.monitor_id}: {signal.detail}"[:200]
                    ):
                        changed = True
                continue

            for claim in signal.covers:
                if claim not in RENEWABLE_CLAIMS:
                    continue
                assumption = updated.assumption(claim)
                if assumption is None or assumption.holds:
                    continue
                assumption.holds = True
                assumption.invalidated_reason = ""
                assumption.established_at = time.time()
                assumption.evidence = f"{signal.monitor_id}: {signal.detail}"[:200]
                changed = True

        if not changed:
            return lease

        signed = self._signer.sign(updated)
        self._leases[team_name] = signed
        if state.invalidated_claims:
            logger.info(
                "RACP: lease %s assumptions updated (%s)",
                signed.lease_id,
                ", ".join(state.invalidated_claims),
            )
        return signed

    def _renew_for_ttl(
        self, team_name: str, lease: BehaviorLease, state: TrajectoryState
    ) -> BehaviorLease | None:
        """Renew an expired lease when current evidence still supports it.

        Renewal restores nothing that evidence has falsified: a lease whose
        assumptions are broken cannot be repaired by waiting for it to expire
        and re-issuing it.
        """
        if state.critical:
            return None
        context = self._contexts.get(team_name)
        if context is None:
            return None
        renewed = self._compiler.renew(
            lease, context, reason="ttl expiry, evidence re-checked at action boundary"
        )
        self._leases[team_name] = renewed
        return renewed


def new_action(
    kind: ActionKind,
    team_name: str,
    summary: str = "",
    payload: object = None,
    irreversible: bool | None = None,
) -> ProposedAction:
    """Convenience constructor for a proposed action."""
    return ProposedAction(
        action_id=f"act:{uuid.uuid4().hex[:12]}",
        kind=kind,
        team_name=team_name,
        summary=summary,
        payload_digest=ProposedAction.digest(payload) if payload is not None else "",
        irreversible=(kind in IRREVERSIBLE_KINDS) if irreversible is None else irreversible,
    )
