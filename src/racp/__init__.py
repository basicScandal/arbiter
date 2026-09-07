"""Runtime Alignment Control Plane (RACP).

Post-training gives Arbiter a *prior* about how it will behave. RACP turns that
prior into a task-scoped, evidence-backed **behavior lease**: an expiring,
signed statement of what the judge may do for one team's demo, which claims
that permission rests on, and which monitors must keep reporting for it to
stay valid. Every consequential effect passes through a gateway that checks the
lease first, renews it when evidence changes, and refuses when it cannot.

Against prompt injection specifically, this adds three things the detection
pipeline alone cannot provide:

1. **Preflight** proves, before each demo, that the detection policy actually
   in force still catches the attacks it claims to -- catching a gutted or
   mis-loaded policy instead of trusting it.
2. **Independent verification** re-scans the text about to cross the
   privileged-LLM boundary rather than trusting the sanitizer's own report.
3. **Fail-closed effects.** With no valid lease, no score is written, no
   commentary is spoken, and no observation crosses the boundary.
"""

from src.racp.audit import DecisionLog
from src.racp.compiler import LeaseCompiler, TaskContext
from src.racp.estimator import StateEstimator
from src.racp.gateway import ActionGateway, new_action
from src.racp.models import (
    ActionKind,
    BehaviorLease,
    Decision,
    DecisionOutcome,
    LeaseState,
    PreflightReport,
    ProposedAction,
)
from src.racp.monitors import Evidence, MonitorEnsemble, default_monitors
from src.racp.pipeline import RACPPipeline
from src.racp.preflight import PreflightEvaluator
from src.racp.signing import LeaseSigner

__all__ = [
    "ActionGateway",
    "ActionKind",
    "BehaviorLease",
    "Decision",
    "DecisionLog",
    "DecisionOutcome",
    "Evidence",
    "LeaseCompiler",
    "LeaseSigner",
    "LeaseState",
    "MonitorEnsemble",
    "PreflightEvaluator",
    "PreflightReport",
    "ProposedAction",
    "RACPPipeline",
    "StateEstimator",
    "TaskContext",
    "default_monitors",
    "new_action",
]
