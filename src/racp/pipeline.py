"""Event-driven wiring for the Runtime Alignment Control Plane.

Subscribes to the capture event bus and keeps the gateway's leases in step with
what is actually happening in the room:

* ``demo_started`` -- run preflight against the live detector and issue a lease
  for the new team. A failing preflight yields a quarantined lease, which means
  every consequential effect for that demo fails closed.
* ``injection_detected`` -- falsify the no-injection assumption immediately, so
  the evidence is already on the lease when the next action is proposed rather
  than being discovered afterwards.
* ``demo_stopped`` -- nothing is renewed here on purpose: the boundary-crossing
  authorization that follows re-checks evidence itself.

The pipeline owns the gateway instance; the defense, scoring, and commentary
pipelines are handed the same object so all of them enforce against one lease.
"""

from __future__ import annotations

import logging

from src.capture.event_bus import EventBus
from src.capture.models import DemoStarted, DemoStopped
from src.defense.injection_detector import InjectionDetector
from src.defense.models import InjectionDetected
from src.racp.audit import DecisionLog
from src.racp.compiler import CLAIM_NO_INJECTION, LeaseCompiler, TaskContext
from src.racp.gateway import ActionGateway
from src.racp.models import LeaseInvalidated, LeaseIssued, LeaseQuarantined
from src.racp.monitors import MonitorEnsemble, default_monitors
from src.racp.preflight import PreflightEvaluator
from src.racp.signing import LeaseSigner

logger = logging.getLogger(__name__)


class RACPPipeline:
    """Issues, renews, and invalidates behavior leases from capture events.

    Args:
        detector: The detector instance wired into the defense pipeline.
            Preflight must exercise the policy actually in force, so this
            should be the live object rather than a fresh one.
        model: Identifier of the privileged judging model, recorded on leases.
        decisions_path: Optional JSONL path for the hash-chained decision log.
        enforce: When False the gateway runs in shadow mode.
        track_lookup: Optional callable returning a team's track, used to shape
            preflight probes and the lease objective.
    """

    def __init__(
        self,
        detector: InjectionDetector | None = None,
        model: str = "",
        decisions_path: str | None = "data/racp/decisions.jsonl",
        enforce: bool = True,
        track_lookup=None,
    ) -> None:
        self._detector = detector or InjectionDetector()
        self._model = model
        self._track_lookup = track_lookup

        signer = LeaseSigner()
        self.gateway = ActionGateway(
            compiler=LeaseCompiler(signer),
            signer=signer,
            log=DecisionLog(decisions_path),
            monitors=MonitorEnsemble(default_monitors(self._detector)),
            enforce=enforce,
        )
        self._preflight = PreflightEvaluator(self._detector)
        self._event_bus: EventBus | None = None
        self._current_team: str = ""

    # -- wiring -------------------------------------------------------------

    async def setup(self, event_bus: EventBus) -> None:
        """Subscribe to the capture events that drive lease lifecycle."""
        self._event_bus = event_bus
        event_bus.subscribe("demo_started", self._on_demo_started)
        event_bus.subscribe("injection_detected", self._on_injection_detected)
        event_bus.subscribe("demo_stopped", self._on_demo_stopped)
        logger.info(
            "RACP control plane armed (%s)",
            "enforcing" if self.gateway.enforcing else "shadow mode",
        )

    def policy_names(self) -> list[str]:
        """Names of the detection patterns currently loaded."""
        return [p.name for p in self._detector.patterns]

    # -- event handlers -----------------------------------------------------

    async def _on_demo_started(self, event: DemoStarted) -> None:
        """Preflight the live policy, then issue a lease for the new demo."""
        self._current_team = event.team_name
        track = ""
        if self._track_lookup is not None:
            try:
                track = self._track_lookup(event.team_name) or ""
            except Exception:  # noqa: BLE001 - a bad lookup must not block issuance
                logger.warning("RACP track lookup failed", exc_info=True)

        context = TaskContext(
            team_name=event.team_name,
            track=track,
            model=self._model,
            policy_names=self.policy_names(),
        )

        report = self._preflight.run(event.team_name, track)
        lease = self.gateway.issue(context, report)

        if self._event_bus is None:
            return
        if report.passed:
            self._event_bus.publish(
                LeaseIssued(
                    lease=lease,
                    reason=f"demo started for {event.team_name}",
                )
            )
        else:
            self._event_bus.publish(
                LeaseQuarantined(
                    lease_id=lease.lease_id,
                    team_name=event.team_name,
                    report=report,
                )
            )

    async def _on_injection_detected(self, event: InjectionDetected) -> None:
        """Record injection evidence against the lease as soon as it is seen."""
        team = event.attempt.team_name or self._current_team
        if not team:
            return
        lease = self.gateway.invalidate(
            team,
            [CLAIM_NO_INJECTION],
            reason=(
                f"{event.attempt.confidence} confidence {event.attempt.injection_type} "
                f"injection [{event.attempt.pattern}]"
            ),
        )
        if lease is None or self._event_bus is None:
            return
        self._event_bus.publish(
            LeaseInvalidated(
                lease_id=lease.lease_id,
                team_name=team,
                claims=[CLAIM_NO_INJECTION],
                reason=f"{event.attempt.confidence} confidence injection attempt",
            )
        )

    async def _on_demo_stopped(self, event: DemoStopped) -> None:
        """Log the lease state at demo end; renewal happens at the next action."""
        lease = self.gateway.lease_for(event.team_name)
        if lease is None:
            return
        stale = [a.claim for a in lease.stale_assumptions()]
        logger.info(
            "RACP lease %s r%d at demo stop for %s: %s",
            lease.lease_id,
            lease.revision,
            event.team_name,
            f"stale claims: {', '.join(stale)}" if stale else "all assumptions hold",
        )
