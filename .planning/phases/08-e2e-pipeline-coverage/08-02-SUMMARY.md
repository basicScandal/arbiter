---
phase: 08-e2e-pipeline-coverage
plan: 02
subsystem: testing
tags: [moe, event-bus, scoring, wiring, regression, e2e]

# Dependency graph
requires:
  - phase: 07-test-infrastructure
    provides: EventCollector, conftest fixtures, asyncio_mode=auto
provides:
  - "E2E-02: MoE multi-provider scoring through ScoringPipeline event path"
  - "E2E-03: Event wiring regression tests for all 13 sub-pipeline subscriptions"
  - "Subscriber count regression guard catching additions/removals"
affects: [09-groq-rehearsal, 10-dashboard-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mock LLM provider pattern for MoE testing"
    - "EventBus subscription count assertion as regression guard"
    - "Handler replacement with AsyncMock for responsive wiring tests"

key-files:
  created:
    - tests/test_e2e_moe_scoring.py
    - tests/test_e2e_event_wiring.py
  modified: []

key-decisions:
  - "13 sub-pipeline subscriptions (not 14) - accurate recount: defense(4)+commentary(5)+scoring(2)+deliberation(2)"
  - "Scoped wiring tests to 4 sub-pipelines; 8 CapturePipeline-direct subscriptions covered by existing unit tests"

patterns-established:
  - "Handler replacement pattern: AsyncMock handlers + re-wire to verify responsiveness"
  - "CommentaryPipeline mock init pattern: patch __init__ + set required attributes for setup()"

# Metrics
duration: 5min
completed: 2026-02-17
---

# Phase 8 Plan 2: MoE Scoring & Event Wiring E2E Summary

**MoE 3-provider scoring E2E through ScoringPipeline event bus, plus wiring regression tests verifying all 13 sub-pipeline EventBus subscriptions with count guard**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-17T10:33:48Z
- **Completed:** 2026-02-17T10:39:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Validated MoE scoring with 3 mock providers through the full ScoringPipeline event bus path (not direct engine call)
- Verified all 13 sub-pipeline EventBus subscriptions are registered and responsive to trigger events
- Added subscriber count regression guard that catches silent wiring regressions (event name typos, missing subscribe calls)
- All 388 tests pass sequentially and in parallel (pytest -n auto)

## Task Commits

Each task was committed atomically:

1. **Task 1: MoE integration test through pipeline event path** - `827af55` (feat)
2. **Task 2: Event wiring regression tests** - `57ed960` (feat)

## Files Created/Modified
- `tests/test_e2e_moe_scoring.py` - 4 tests: 3-provider pipeline path, aggregated scores, partial failure, full failure fallback
- `tests/test_e2e_event_wiring.py` - 6 tests: subscription registration, responsive handlers for all 4 sub-pipelines, count regression guard

## Decisions Made
- Confirmed 13 subscriptions (not 14 as research stated) across 4 sub-pipelines: defense(4)+commentary(5)+scoring(2)+deliberation(2)
- Scoped to sub-pipeline setup() wiring only; CapturePipeline-direct subscriptions already covered by unit tests
- Used handler replacement + re-wire pattern rather than spy pattern for cleaner responsive tests

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All E2E pipeline coverage tests complete (E2E-01 through E2E-04 across plans 01 and 02)
- Phase 8 complete, ready for Phase 9 (Groq fallback + rehearsal) and Phase 10 (dashboard hardening)
- MoE ensemble scoring blocker resolved: now tested with real multi-provider pipeline path

---
*Phase: 08-e2e-pipeline-coverage*
*Completed: 2026-02-17*
