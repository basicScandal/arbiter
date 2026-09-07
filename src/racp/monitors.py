"""Independent evidence monitors for the control plane.

Each monitor answers one narrow, checkable question about the current
trajectory and returns a :class:`MonitorSignal`. Monitors are deliberately
diverse in kind -- counting, re-scanning, hashing, comparing claimed effects to
observed ones -- so that a single failure mode does not blind all of them at
once.

Two properties matter more than any individual check:

* **No monitor authorizes anything.** They produce evidence; the gateway
  decides. A monitor that cannot run is itself critical evidence
  (``monitor_unavailable``), never a silent skip.
* **The residue monitor verifies effects, not claims.** It re-scans the text
  that is actually about to cross the privileged-LLM boundary rather than
  trusting the sanitizer's report that it removed everything.
"""

from __future__ import annotations

import hashlib
import logging

from pydantic import BaseModel

from src.defense.injection_detector import InjectionDetector
from src.defense.models import InjectionAttempt
from src.racp.compiler import (
    CLAIM_BUDGET,
    CLAIM_MONITORS_HEALTHY,
    CLAIM_NO_INJECTION,
    CLAIM_OBSERVATION_PROVENANCE,
    CLAIM_POLICY_INTACT,
    CLAIM_SANITIZER_CLEAN,
    CLAIM_TEAM_IDENTITY,
)
from src.racp.models import BehaviorLease, MonitorSignal, Severity

logger = logging.getLogger(__name__)


class Evidence(BaseModel):
    """Observed state gathered for one authorization decision.

    Populated by the caller at the enforcement point. Fields left at their
    defaults simply produce no signal from the monitor that reads them -- with
    the exception of the policy hash, whose absence is itself a finding.
    """

    team_name: str = ""
    injection_attempts: list[InjectionAttempt] = []
    observations: list[str] = []
    transcripts: list[str] = []
    ocr_texts: list[str] = []
    policy_names: list[str] = []
    observation_count: int = 0

    def policy_hash(self) -> str:
        """Hash of the detection policy currently loaded."""
        joined = "|".join(sorted(self.policy_names))
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


class Monitor:
    """Base class for evidence monitors."""

    monitor_id: str = "monitor"
    # Lease claims this monitor is responsible for. Reported on every signal so
    # a clean reading can re-establish a renewable claim, not only falsify one.
    claims: tuple[str, ...] = ()

    def evaluate(self, lease: BehaviorLease, evidence: Evidence) -> MonitorSignal:
        raise NotImplementedError


class InjectionEvidenceMonitor(Monitor):
    """Counts detected injection attempts against this demo."""

    monitor_id = "injection_evidence"
    claims = (CLAIM_NO_INJECTION,)

    def evaluate(self, lease: BehaviorLease, evidence: Evidence) -> MonitorSignal:
        high = [a for a in evidence.injection_attempts if a.confidence == "high"]
        medium = [a for a in evidence.injection_attempts if a.confidence == "medium"]

        if high:
            return MonitorSignal(
                monitor_id=self.monitor_id,
                triggered=True,
                severity=Severity.HIGH,
                detail=f"{len(high)} high-confidence injection attempt(s) in this demo",
                weight=0.25 + 0.05 * min(len(high), 5),
                invalidates=[CLAIM_NO_INJECTION],
            )
        if len(medium) >= 2:
            return MonitorSignal(
                monitor_id=self.monitor_id,
                triggered=True,
                severity=Severity.MEDIUM,
                detail=f"{len(medium)} medium-confidence injection attempts accumulated",
                weight=0.15,
                invalidates=[CLAIM_NO_INJECTION],
            )
        if medium:
            return MonitorSignal(
                monitor_id=self.monitor_id,
                triggered=True,
                severity=Severity.LOW,
                detail="1 medium-confidence injection attempt",
                weight=0.05,
            )
        return MonitorSignal(
            monitor_id=self.monitor_id, triggered=False, detail="no injection evidence"
        )


class SanitizerResidueMonitor(Monitor):
    """Re-scans the text about to cross the privileged-LLM boundary.

    The sanitizer reports that it removed every tainted entry. This monitor
    checks that claim against the artifact itself. Residue here means the
    boundary failed, which is the most serious finding the control plane can
    make -- the privileged judge is one step from reading attacker text.
    """

    monitor_id = "sanitizer_residue"
    claims = (CLAIM_SANITIZER_CLEAN,)

    def __init__(self, detector: InjectionDetector | None = None) -> None:
        self._detector = detector or InjectionDetector()

    def evaluate(self, lease: BehaviorLease, evidence: Evidence) -> MonitorSignal:
        residue: list[str] = []
        for observation in evidence.observations:
            if self._detector.scan_observation(observation).is_injection:
                residue.append("observation")
        for transcript in evidence.transcripts:
            if self._detector.scan(transcript, source="verbal").is_injection:
                residue.append("transcript")

        if residue:
            return MonitorSignal(
                monitor_id=self.monitor_id,
                triggered=True,
                severity=Severity.CRITICAL,
                detail=(
                    f"{len(residue)} sanitized entr(y/ies) still match injection "
                    f"patterns ({', '.join(sorted(set(residue)))})"
                ),
                weight=0.6,
                invalidates=[CLAIM_SANITIZER_CLEAN],
            )
        return MonitorSignal(
            monitor_id=self.monitor_id,
            triggered=False,
            detail=f"{len(evidence.observations)} observations verified clean",
        )


class ObservationProvenanceMonitor(Monitor):
    """Flags observations that mirror slide text rather than demo behaviour.

    "Observation laundering": a team puts evaluative prose on a slide, the
    quarantined model faithfully transcribes it, and the judge reads praise it
    believes it observed. The text may contain no injection pattern at all,
    which is why provenance is checked separately from detection.
    """

    monitor_id = "observation_provenance"
    claims = (CLAIM_OBSERVATION_PROVENANCE,)

    def __init__(self, detector: InjectionDetector | None = None) -> None:
        self._detector = detector or InjectionDetector()

    def evaluate(self, lease: BehaviorLease, evidence: Evidence) -> MonitorSignal:
        if not evidence.ocr_texts or not evidence.observations:
            return MonitorSignal(
                monitor_id=self.monitor_id,
                triggered=False,
                detail="no slide text to cross-reference",
            )

        conflicts: list[str] = []
        for observation in evidence.observations:
            suspicious, detail = self._detector.cross_reference_observation(
                observation, evidence.ocr_texts
            )
            if suspicious:
                conflicts.append(detail)

        if conflicts:
            return MonitorSignal(
                monitor_id=self.monitor_id,
                triggered=True,
                severity=Severity.MEDIUM,
                detail=f"{len(conflicts)} observation(s) mirror slide text: {conflicts[0][:120]}",
                weight=0.2,
                invalidates=[CLAIM_OBSERVATION_PROVENANCE],
            )
        return MonitorSignal(
            monitor_id=self.monitor_id, triggered=False, detail="observation provenance clean"
        )


class PolicyIntegrityMonitor(Monitor):
    """Detects the detection policy changing under a live lease.

    The lease was preflighted against a specific pattern set. If a plugin
    reloads, a pattern is added, or the detector is swapped, the evidence
    behind the lease no longer describes the system in force.

    The monitor reads the live detector directly when it has one. Asking each
    enforcement point to self-report the policy it is running under is weaker
    evidence and easy to forget: a call site that omits it would look identical
    to a policy that vanished.

    Args:
        detector: The detector actually in force. Falls back to the policy the
            caller reported in ``Evidence`` when absent.
    """

    monitor_id = "policy_integrity"
    claims = (CLAIM_POLICY_INTACT,)

    def __init__(self, detector: InjectionDetector | None = None) -> None:
        self._detector = detector

    def _policy_hashes(self, evidence: Evidence) -> dict[str, str]:
        """Every available view of the policy in force, by source.

        Both sources are checked because they fail differently: reading the
        detector catches its pattern set being mutated, while the enforcement
        point's self-report catches the detector *reference* being swapped for a
        different object. Either disagreeing with the lease is a finding.
        """
        hashes: dict[str, str] = {}
        if self._detector is not None:
            names = sorted(p.name for p in self._detector.patterns)
            hashes["detector"] = hashlib.sha256(
                "|".join(names).encode("utf-8")
            ).hexdigest()[:16]
        if evidence.policy_names:
            hashes["enforcement point"] = evidence.policy_hash()
        return hashes

    def evaluate(self, lease: BehaviorLease, evidence: Evidence) -> MonitorSignal:
        expected = ""
        for entry in lease.policy_provenance:
            if entry.startswith("detector:"):
                expected = entry.split(":", 1)[1]
                break

        if not expected:
            return MonitorSignal(
                monitor_id=self.monitor_id,
                triggered=True,
                severity=Severity.HIGH,
                detail="lease carries no detector provenance",
                weight=0.3,
                invalidates=[CLAIM_POLICY_INTACT],
            )
        hashes = self._policy_hashes(evidence)
        if not hashes:
            # Neither a live detector nor a self-reported policy: we cannot
            # confirm the lease still describes the running system.
            return MonitorSignal(
                monitor_id=self.monitor_id,
                triggered=True,
                severity=Severity.MEDIUM,
                detail="no live policy available for comparison",
                weight=0.15,
                invalidates=[CLAIM_POLICY_INTACT],
            )

        drift = {src: h for src, h in hashes.items() if h != expected}
        if drift:
            source, actual = next(iter(drift.items()))
            return MonitorSignal(
                monitor_id=self.monitor_id,
                triggered=True,
                severity=Severity.CRITICAL,
                detail=f"policy changed under lease ({source}): {expected} -> {actual}",
                weight=0.5,
                invalidates=[CLAIM_POLICY_INTACT],
            )
        return MonitorSignal(
            monitor_id=self.monitor_id,
            triggered=False,
            detail=f"policy {expected} intact ({', '.join(sorted(hashes))})",
        )


class IdentityMonitor(Monitor):
    """Verifies the action belongs to the team the lease was issued for.

    Catches cross-demo bleed: a late scorecard, roast, or commentary task from
    the previous team arriving after the next team has started.
    """

    monitor_id = "identity"
    claims = (CLAIM_TEAM_IDENTITY,)

    def evaluate(self, lease: BehaviorLease, evidence: Evidence) -> MonitorSignal:
        lease_team = lease.task.get("team_name", "")
        if evidence.team_name and lease_team and evidence.team_name != lease_team:
            return MonitorSignal(
                monitor_id=self.monitor_id,
                triggered=True,
                severity=Severity.HIGH,
                detail=(
                    f"action targets {evidence.team_name!r} but lease covers "
                    f"{lease_team!r}"
                ),
                weight=0.4,
                invalidates=[CLAIM_TEAM_IDENTITY],
            )
        return MonitorSignal(
            monitor_id=self.monitor_id, triggered=False, detail="team identity matches"
        )


class BudgetMonitor(Monitor):
    """Enforces the lease's action and volume budgets."""

    monitor_id = "budget"
    claims = (CLAIM_BUDGET,)

    def evaluate(self, lease: BehaviorLease, evidence: Evidence) -> MonitorSignal:
        budgets = lease.capabilities.budgets
        max_attempts = budgets.get("max_injection_attempts", 0.0)
        max_observations = budgets.get("max_observations", 0.0)

        attempts = len(evidence.injection_attempts)
        observations = evidence.observation_count or len(evidence.observations)

        exceeded: list[str] = []
        if max_attempts and attempts > max_attempts:
            exceeded.append(f"injection attempts {attempts} > {int(max_attempts)}")
        if max_observations and observations > max_observations:
            exceeded.append(f"observations {observations} > {int(max_observations)}")

        if exceeded:
            return MonitorSignal(
                monitor_id=self.monitor_id,
                triggered=True,
                severity=Severity.MEDIUM,
                detail="; ".join(exceeded),
                weight=0.2,
                invalidates=[CLAIM_BUDGET],
            )
        return MonitorSignal(
            monitor_id=self.monitor_id, triggered=False, detail="within budget"
        )


class MonitorEnsemble:
    """Runs every monitor and collects their signals.

    A monitor that raises is reported as unavailable rather than skipped: lost
    coverage is evidence, and it invalidates the monitors-healthy assumption so
    the gateway falls back to its fail-closed path.
    """

    def __init__(self, monitors: list[Monitor] | None = None) -> None:
        self._monitors = monitors if monitors is not None else default_monitors()

    def evaluate(self, lease: BehaviorLease, evidence: Evidence) -> list[MonitorSignal]:
        """Return one signal per monitor, in registration order."""
        signals: list[MonitorSignal] = []
        for monitor in self._monitors:
            try:
                signal = monitor.evaluate(lease, evidence)
                if not signal.covers:
                    signal.covers = list(getattr(monitor, "claims", ()))
                signals.append(signal)
            except Exception as exc:  # noqa: BLE001 - lost coverage is a finding
                logger.exception("RACP monitor %s failed", monitor.monitor_id)
                signals.append(
                    MonitorSignal(
                        monitor_id=monitor.monitor_id,
                        triggered=True,
                        severity=Severity.CRITICAL,
                        detail=f"monitor unavailable: {type(exc).__name__}",
                        weight=0.5,
                        invalidates=[CLAIM_MONITORS_HEALTHY],
                        covers=[CLAIM_MONITORS_HEALTHY],
                    )
                )
        return signals


def default_monitors(detector: InjectionDetector | None = None) -> list[Monitor]:
    """Build the standard monitor set, sharing one detector instance."""
    shared = detector or InjectionDetector()
    return [
        InjectionEvidenceMonitor(),
        SanitizerResidueMonitor(shared),
        ObservationProvenanceMonitor(shared),
        PolicyIntegrityMonitor(shared),
        IdentityMonitor(),
        BudgetMonitor(),
    ]
