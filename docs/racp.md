# Runtime Alignment Control Plane (RACP)

Arbiter's injection defense is a detection pipeline: OCR and transcript
scanning, regex plus semantic classification, sanitization before the
privileged LLM. That pipeline answers one question — *is this text an attack?*
— and answers it well. It cannot answer the question that follows: **is the
judge still authorized to act on what it just read?**

RACP adds that second layer. Post-training gives Arbiter a *prior* about how it
behaves. RACP turns that prior into a **behavior lease**: a signed, expiring,
task-scoped statement of what the judge may do for one team's demo, which
claims that permission rests on, and which monitors must keep reporting for it
to stay valid. Every consequential effect passes through a gateway that checks
the lease first.

For the mechanical walkthrough — the authorization path step by step, the lease
state machine, the monitor contract, and how to gate a new effect — see
[docs/racp-internals.md](racp-internals.md).

## What it adds over detection alone

| Failure the detector cannot catch by itself | What RACP does |
|---|---|
| The detection policy itself is broken — a plugin dropped patterns, a detector was swapped for a stub | **Preflight** runs a task-shaped probe suite plus mutation tests against the *live* detector before every demo. A policy that cannot catch the probes never gets an active lease. |
| The sanitizer reports "clean" and is wrong | The **residue monitor** re-scans the artifact that is actually about to cross the boundary, rather than trusting the sanitizer's own report. |
| The model parrots evaluative slide text back as if it observed it | The **provenance monitor** cross-references observations against accumulated OCR text; no injection pattern needs to be present. |
| A late effect from the previous team lands after the next one starts | The **identity monitor** refuses effects whose team does not match the lease. |
| The policy changes mid-event, under a lease that was granted for a different one | The **policy-integrity monitor** compares the live pattern hash to the lease provenance and terminates on divergence. |
| Something goes wrong in a way nobody enumerated | Effects **fail closed**: no valid lease means no observation crosses the boundary, no score is written, and nothing is spoken. |

## The lease

```json
{
  "lease_id": "lease:9f2c…",
  "revision": 3,
  "subject":  {"agent": "arbiter-judge", "model": "…", "harness": "…"},
  "task":     {"team_name": "Team Nebula", "track": "ROGUE::AGENT", "objective_hash": "…"},
  "capabilities": {"allow": ["publish_observations", "score_demo", …], "budgets": {…}},
  "assumptions": [
    {"claim": "detection_policy_matches_preflighted_policy", "evidence": "policy_hash=…", "holds": true},
    {"claim": "sanitizer_output_is_clean", "holds": true},
    {"claim": "no_injection_in_demo_input", "holds": false,
     "invalidated_reason": "high confidence visual injection [ignore_previous]"}
  ],
  "expires_at": 1788740000.0,
  "signature": "hmac-sha256:…"
}
```

"Alignment" is deliberately never a single boolean. Each claim carries its own
evidence and its own expiry, because a stale slide-provenance check and an
expired lease are different failures with different remedies.

The signature covers everything that grants authority — capabilities,
assumptions, expiry, revision, task. Widening any of them by hand breaks
verification, and an unverifiable lease terminates the trajectory.

## Decision outcomes

More than allow/deny, so a live event degrades instead of stopping:

| Outcome | Meaning in Arbiter |
|---|---|
| `ALLOW` | Effect proceeds under the current lease. |
| `TRANSFORM` | Effect proceeds with a narrowed payload — residue stripped, demo marked `degraded`. |
| `REQUIRE_EVIDENCE` | A required monitor is unavailable; the effect waits for coverage. |
| `REQUIRE_APPROVAL` | Irreversible effect on a compromised trajectory — the operator adjudicates. |
| `DENY` | Effect refused; the pipeline may replan (e.g. score without commentary). |
| `TERMINATE` | Lease revoked. Used for policy divergence and signature failure. |

`SANDBOX` exists in the model but has no live effect to route into yet.

## Where the gates sit

```
demo_started ─→ preflight ─→ lease issued (or quarantined)
                                  │
  key frames / transcripts ───────┼──→ injection_detected ─→ claim falsified
                                  │
  demo_stopped ─→ sanitize ─→ [ PUBLISH_OBSERVATIONS ] ─→ observation_verified
                                  │                            │
                                  │                            ├─→ [ SCORE_DEMO ] ─→ [ PERSIST_SCORE ]
                                  │                            └─→ [ SPEAK_COMMENTARY ]
                                  ▼
                          hash-chained decision log
```

Four enforcement points, all in `src/racp/gateway.py`:

- `PUBLISH_OBSERVATIONS` — `src/defense/pipeline.py`, the privileged-LLM boundary
- `SCORE_DEMO`, `PERSIST_SCORE` — `src/scoring/pipeline.py`
- `SPEAK_COMMENTARY` — `src/commentary/pipeline.py`

Each refusal publishes `racp_action_blocked` to the event bus, which the
operator dashboard renders alongside the ruling and its evidence.

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `RACP_ENABLED` | `true` | Wire the control plane into the capture pipeline. |
| `RACP_ENFORCE` | `true` | When `false`, run in shadow mode: decisions computed and logged, nothing blocked. |
| `ARBITER_RACP_SECRET` | *(random per process)* | Lease signing key. |

The decision log is written to `data/racp/decisions.jsonl` as a hash chain;
`DecisionLog.verify_chain()` detects an edited or deleted entry. Attacker-
controlled text is never written to it — only digests, pattern names, and
monitor identifiers.

## Rolling it out

1. Run rehearsals with `RACP_ENFORCE=false` and read the log: every entry with a
   `shadow_outcome` is an effect enforcement would have stopped.
2. Confirm the block rate on benign demos is zero. A caught injection alone must
   never block a demo — teams attack the judge on purpose here, and a successful
   defense is not a reason to refuse to judge them.
3. Turn enforcement on. Preflight failures and policy divergence are the two
   rulings that stop a demo outright; both mean the defense itself is not in the
   state it claims, which is worth stopping for.

## Does it actually prevent anything?

`scripts/racp_experiment.py` runs four controllers over identical demo
trajectories, using Arbiter's real detector, sanitizer, monitors, and gateway.
Attack text comes from the project's own injection corpus; benign text comes
from that corpus's false-positive set. Safety is judged by an oracle that reads
the scenario's ground truth and never consults a lease.

```bash
uv run python scripts/racp_experiment.py --scenarios 1500 --seed 20260906
```

| Controller | Violations prevented | 95% CI | False blocks | p95 decision |
|---|---:|---:|---:|---:|
| No control | 0.0% | 0.0–0.0% | 0.0% | — |
| Static startup policy | 14.3% | 12.2–16.3% | 0.0% | 350 µs |
| Dynamic lease | 71.4% | 68.8–74.2% | 0.0% | 599 µs |
| Dynamic lease + preflight | **85.7%** | 83.6–87.8% | 0.0% | 658 µs |

Reading the numbers honestly:

- **85.7% is the ceiling, not a shortfall.** One scenario family is
  deliberately unobservable — a demo that is harmful for reasons nothing
  encodes. The full control plane catches every unsafe scenario that any
  observable check could catch, and nothing beyond that.
- **Renewal is what most of the gain buys.** A policy compiled at demo start
  and never re-checked catches only the failure that is visible at start (a
  monitor that cannot run at all). Everything that arrives later — residue at
  the boundary, a swapped policy, a late effect from the previous team — needs
  evidence re-read at the action boundary.
- **Preflight adds the defective-policy family.** Those 14 points are cases a
  gutted detector would happily approve; recompiling the same broken policy on
  every renewal reproduces the defect rather than finding it.
- **Zero false blocks on benign demos**, including teams talking about
  injection defenses on stage — but that is a property of clean synthetic
  controls, not proof that production utility is unaffected.
- **Sub-millisecond decisions**, two orders of magnitude inside the 50 ms
  budget for something sitting in front of a live demo.

This measures the control mechanism. It says nothing about value alignment, and
the numbers are not an estimate for agents in general.

## What this does not do

Being precise about the boundary matters more than the feature list:

- **It is not value alignment.** If a harmful property is not observable and not
  encoded, the gateway cannot enforce it. RACP constrains *effects*, and says
  nothing about what the model wants.
- **Monitors are fallible sensors, not authorities.** A compromised sensor or an
  omitted event produces false evidence. No single monitor authorizes an
  irreversible effect on its own, but the ensemble is not tamper-proof.
- **Preflight does not prove the policy is complete.** Mutation testing shows the
  probe suite notices each pattern's removal; it cannot show that the pattern set
  covers every attack.
- **Effects outside the gateway are unmediated.** Cross-team deliberation
  publishes rankings on a session scope, not a per-demo lease, and is not gated.
  Anything added later that produces an external effect must be routed through
  `ActionGateway.authorize` or it is simply outside the boundary.
- **The risk score is not calibrated.** It is an interpretable sum of monitor
  evidence weights. Calling it a posterior would require labelled incidents from
  real events.
- **TOCTOU is only partly addressed.** Decisions are made on evidence gathered at
  the enforcement point, immediately before the effect, but the gateway does not
  yet issue capability tokens bound to exact arguments.

## Tests

```bash
uv run pytest tests/test_racp_lease.py tests/test_racp_preflight.py \
              tests/test_racp_monitors.py tests/test_racp_gateway.py \
              tests/test_racp_integration.py
```

The integration suite runs full demos through the real defense pipeline: a clean
one, one carrying an injection the sanitizer catches, one where the sanitizer is
subverted, one where the policy is gutted, and one where the policy is swapped
mid-demo.
