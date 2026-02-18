# Roadmap: Arbiter

## Milestones

- ✅ **v1.0 MVP** — Phases 1-6 (shipped 2026-02-16)
- 🚧 **v1.1 Reliability & Polish** — Phases 7-10 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-6) — SHIPPED 2026-02-16</summary>

- [x] Phase 1: Capture Layer (4/4 plans) — completed 2026-02-15
- [x] Phase 2: Defense Pipeline (3/3 plans) — completed 2026-02-15
- [x] Phase 3: Commentary + Output (3/3 plans) — completed 2026-02-15
- [x] Phase 4: Scoring System (3/3 plans) — completed 2026-02-16
- [x] Phase 5: Memory + Deliberation (3/3 plans) — completed 2026-02-16
- [x] Phase 6: Venue Hardening (3/3 plans) — completed 2026-02-16

See: `.planning/milestones/v1.0-ROADMAP.md` for full details.

</details>

### 🚧 v1.1 Reliability & Polish (In Progress)

**Milestone Goal:** Harden the system for live event reliability — full test coverage, rehearsal mode, fallback coverage, MoE ensemble E2E, and operator dashboard polish.

- [x] **Phase 7: Test Infrastructure** — Timeout guards, EventCollector, singleton reset, parallel test support, VCR cassettes (completed 2026-02-17)
- [x] **Phase 8: E2E Pipeline Coverage** — Full pipeline chain tests, MoE integration, event wiring regression, multi-level task draining (completed 2026-02-17)
- [x] **Phase 9: Groq Fallback + Rehearsal Mode** — Groq scoring provider, MoE timeout hardening, synthetic capture, replay provider, CLI rehearsal (completed 2026-02-17)
- [ ] **Phase 10: Dashboard Hardening** — WebSocket reconnect indicator, health endpoint, scoring event forwarding

## Phase Details

### Phase 7: Test Infrastructure
**Goal**: Tests run reliably, in parallel, with deterministic async assertions and no singleton interference
**Depends on**: Phase 6 (v1.0 complete)
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, TEST-06
**Success Criteria** (what must be TRUE):
  1. An async test that publishes events can assert on downstream effects using EventCollector.wait_for() instead of sleep-based polling
  2. A test that hangs on an unawaited task is killed by pytest-timeout within 30 seconds instead of blocking CI forever
  3. Running the full test suite twice in a row produces identical results — no singleton state leaks between tests
  4. `pytest -m integration` runs only integration tests; `pytest -m "not integration"` runs only unit tests
  5. `pytest -n auto` distributes tests across CPU cores without interference or shared-state failures
**Plans:** 2 plans

Plans:
- [x] 07-01-PLAN.md — Core test config, dependencies, conftest.py fixtures, EventCollector helper
- [x] 07-02-PLAN.md — Parallel execution validation (pytest-xdist) and VCR.py cassette infrastructure

### Phase 8: E2E Pipeline Coverage
**Goal**: The full event pipeline from capture through deliberation is covered by automated tests that catch wiring regressions
**Depends on**: Phase 7
**Requirements**: E2E-01, E2E-02, E2E-03, E2E-04
**Success Criteria** (what must be TRUE):
  1. A test drives a synthetic demo through the entire pipeline (capture -> defense -> commentary -> scoring -> deliberation) and asserts the correct events fire in order
  2. A test validates MoE scoring with 3 mock providers returning different scores, and ScoreAggregator produces a weighted result
  3. A test verifies that all EventBus subscriptions wired in CapturePipeline.setup() are connected and responsive to their trigger events
  4. A test that publishes an event triggering a two-level create_task chain (e.g., observation_verified -> score() -> scoring_complete) correctly drains all task depths before asserting
**Plans:** 2 plans

Plans:
- [x] 08-01-PLAN.md — Full pipeline chain E2E test + multi-level task draining tests (E2E-01, E2E-04)
- [x] 08-02-PLAN.md — MoE integration through pipeline event path + event wiring regression tests (E2E-02, E2E-03)

### Phase 9: Groq Fallback + Rehearsal Mode
**Goal**: Scoring pipeline has a working fallback when Gemini is unavailable, and operators can rehearse the full system without live hardware or API keys
**Depends on**: Phase 8
**Requirements**: REL-01, REL-02, REL-03, RHS-01, RHS-02, RHS-03
**Success Criteria** (what must be TRUE):
  1. When Gemini scoring fails, GroqProvider produces valid rubric scores through the same LLMProvider interface — visible as a successful score in ScoreStore
  2. MoE scoring completes within 15 seconds even when one provider hangs — slow providers are cancelled, partial results are aggregated
  3. Running `python -m arbiter --rehearsal` (or equivalent CLI flag) executes a full demo cycle with synthetic camera/audio and deterministic LLM responses, producing commentary and scores without any real hardware or API calls
  4. An operator can trigger rehearsal mode from the dashboard and watch the full theatrical flow (commentary -> score reveal -> deliberation) play out with mock data
**Plans:** 2 plans

Plans:
- [x] 09-01-PLAN.md — GroqProvider scoring fallback + MoE timeout hardening (REL-01, REL-02, REL-03)
- [x] 09-02-PLAN.md — Rehearsal mode: synthetic capture, replay provider, CLI + dashboard integration (RHS-01, RHS-02, RHS-03)

### Phase 10: Dashboard Hardening
**Goal**: The operator dashboard is reliable under real venue conditions — survives WiFi blips, shows system health, and streams scoring events live
**Depends on**: Phase 7 (uses test infrastructure; independent of Phases 8-9)
**Requirements**: DASH-01, DASH-02, DASH-03
**Success Criteria** (what must be TRUE):
  1. When the WebSocket connection drops, the dashboard shows a visible "reconnecting" indicator and automatically reconnects without operator intervention
  2. The operator can see per-component health status (TTS, Gemini, scoring providers) on the dashboard at a glance
  3. When a demo finishes scoring, the scoring result appears on the operator dashboard in real-time without manual refresh
**Plans:** 3 plans

Plans:
- [x] 10-01-PLAN.md — Backend health endpoint + WS health/scoring push + frontend store/types/hook plumbing
- [x] 10-02-PLAN.md — ReconnectBanner, ConnectionDot update, HealthPanel, ScorePanel enhancement, App layout
- [ ] 10-03-PLAN.md — Gap closure: Reset scorecard state when new demo starts

## Progress

**Execution Order:**
Phases execute in numeric order: 7 -> 8 -> 9 -> 10
(Phase 10 depends only on Phase 7 and could run in parallel with 8-9 if needed.)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Capture Layer | v1.0 | 4/4 | Complete | 2026-02-15 |
| 2. Defense Pipeline | v1.0 | 3/3 | Complete | 2026-02-15 |
| 3. Commentary + Output | v1.0 | 3/3 | Complete | 2026-02-15 |
| 4. Scoring System | v1.0 | 3/3 | Complete | 2026-02-16 |
| 5. Memory + Deliberation | v1.0 | 3/3 | Complete | 2026-02-16 |
| 6. Venue Hardening | v1.0 | 3/3 | Complete | 2026-02-16 |
| 7. Test Infrastructure | v1.1 | 2/2 | Complete | 2026-02-17 |
| 8. E2E Pipeline Coverage | v1.1 | 2/2 | Complete | 2026-02-17 |
| 9. Groq Fallback + Rehearsal | v1.1 | 2/2 | Complete | 2026-02-17 |
| 10. Dashboard Hardening | v1.1 | 2/3 | In progress | - |
