# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** Produce fair, defensible scores alongside human judges -- while being entertaining and resistant to prompt injection from a security-savvy audience.
**Current focus:** Phase 8 — E2E Pipeline Coverage (v1.1 Reliability & Polish)

## Current Position

Milestone: v1.1 Reliability & Polish
Phase: 8 of 10 (E2E Pipeline Coverage)
Plan: 2 of 2 in current phase (PHASE COMPLETE)
Status: Phase 8 complete
Last activity: 2026-02-17 — Completed 08-02 MoE scoring & event wiring E2E tests

Progress: [██████████████████████████░░░░] 80% (19/19 v1.0 plans complete, 4/8 v1.1 plans)

## Performance Metrics

**v1.0 Summary:**
- Total plans completed: 19
- Total phases: 6
- Average duration: 3min/plan
- Total execution time: 0.95 hours
- Timeline: 2 days (2026-02-15 -> 2026-02-16)

**v1.1:**
- Plans completed: 4
- Phases: 4 (Phases 7-10)
- Requirements: 19

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 07    | 01   | 10min    | 3     | 4     |
| 07    | 02   | 3min     | 2     | 1     |
| 08    | 01   | 3min     | 2     | 2     |
| 08    | 02   | 5min     | 2     | 2     |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v1.1 Roadmap]: Test infrastructure before features — EventCollector and timeout guards are foundation for all E2E tests
- [v1.1 Roadmap]: Groq fallback + rehearsal combined into one phase — both use proven patterns, Groq is ~50 LOC
- [v1.1 Roadmap]: Dashboard hardening last — no downstream deps, can parallelize with Phase 8-9 if needed
- [07-01]: In-place singleton reset over object replacement — handles import-time name bindings in pipeline.py
- [07-01]: asyncio_mode=auto — eliminates @pytest.mark.asyncio boilerplate across all test files
- [07-01]: thread timeout method — required for pytest-xdist worker and threaded test compatibility
- [07-02]: No xdist_group markers needed for TUI tests -- Textual headless mode works in isolated workers
- [07-02]: VCR.py compatibility with google-genai confirmed -- httpcore patching covers httpx REST calls
- [08-01]: Mock sub-pipelines directly, not CapturePipeline -- avoids hardware dependencies while testing real EventBus wiring
- [08-01]: No ordering assertions between parallel subscribers -- non-deterministic task scheduling
- [08-01]: Patch asyncio.sleep in scoring pipeline module for fast theatrical reveal tests
- [08-02]: 13 sub-pipeline subscriptions (not 14) -- accurate recount: defense(4)+commentary(5)+scoring(2)+deliberation(2)
- [08-02]: Scoped wiring tests to 4 sub-pipelines; CapturePipeline-direct subscriptions covered by existing unit tests

### Pending Todos

None.

### Blockers/Concerns

- ~~MoE ensemble scoring wired but never tested with real multi-provider setup~~ RESOLVED in 08-02: E2E test validates 3-provider MoE through ScoringPipeline event bus
- Groq JSON format reliability unknown until empirical testing (Phase 9)
- ~~pytest-recording/VCR.py compatibility with google-genai SDK uncertain~~ RESOLVED in 07-02: httpcore patching confirmed working

## Session Continuity

Last session: 2026-02-17
Stopped at: Completed 08-02-PLAN.md (MoE scoring & event wiring E2E tests -- Phase 8 complete)
Resume file: None
