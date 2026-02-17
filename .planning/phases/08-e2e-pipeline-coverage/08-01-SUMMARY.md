---
phase: 08-e2e-pipeline-coverage
plan: 01
subsystem: testing
tags: [pytest, asyncio, event-bus, e2e, eventcollector, create_task, pipeline-chain]

# Dependency graph
requires:
  - phase: 07-test-infrastructure
    provides: "EventCollector, singleton reset, asyncio_mode=auto, pytest-timeout"
provides:
  - "Full pipeline chain E2E test (E2E-01) covering defense -> commentary -> scoring -> deliberation"
  - "Multi-level task draining E2E tests (E2E-04) validating 2-level and 3-level create_task chains"
  - "Parallel subscriber completion verification across 3 sub-pipelines"
  - "EventCollector already-captured fast-path validation"
affects: [08-02-PLAN, phase-09, phase-10]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Full pipeline setup helper reusable across E2E tests (_setup_full_pipeline)"
    - "Patch asyncio.sleep in scoring pipeline for fast theatrical reveal tests"
    - "Async generator mock for CommentaryPipeline._generator.stream_sentences"

key-files:
  created:
    - tests/test_e2e_pipeline_chain.py
    - tests/test_e2e_task_draining.py
  modified: []

key-decisions:
  - "Mock sub-pipeline internals instead of CapturePipeline -- avoids hardware dependencies"
  - "Do NOT assert ordering between parallel subscribers (scoring vs commentary) -- non-deterministic"
  - "Patch asyncio.sleep in scoring pipeline module to eliminate theatrical delays in tests"

patterns-established:
  - "E2E pipeline setup: create pipelines with mocked I/O, call setup(event_bus), drive events manually"
  - "Causal ordering assertions: only assert order between causally dependent events, not parallel ones"
  - "Three-level chain pattern: observation_verified -> commentary_delivered -> score_revealed"

# Metrics
duration: 3min
completed: 2026-02-17
---

# Phase 8 Plan 1: Pipeline Chain & Task Draining E2E Summary

**7 E2E tests driving synthetic demos through all 4 sub-pipelines with causal ordering assertions and multi-level create_task chain draining via EventCollector**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-17T10:33:54Z
- **Completed:** 2026-02-17T10:37:52Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments
- Full pipeline chain E2E test drives a demo through defense -> commentary -> scoring -> deliberation and asserts causal event ordering
- Score reveal chain validated: commentary_delivered triggers detached _reveal_score task publishing score_revealed
- Multi-level create_task chains verified: 2-level (observation_verified -> scoring_complete) and 3-level (through score_revealed)
- Parallel subscriber completion verified across scoring, commentary, and deliberation pipelines
- EventCollector already-captured fast-path validated for immediate return when event already exists
- Empty observations edge case handled gracefully by all sub-pipelines
- All 388 tests pass (7 new E2E + 381 existing) with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Full pipeline chain E2E test (E2E-01)** - `8cc36d5` (test)
2. **Task 2: Multi-level task draining E2E tests (E2E-04)** - `249b840` (test)

## Files Created/Modified
- `tests/test_e2e_pipeline_chain.py` - Full chain E2E: test_full_pipeline_chain, test_full_chain_publishes_score_revealed_after_reveal, test_pipeline_chain_handles_empty_observations_gracefully
- `tests/test_e2e_task_draining.py` - Task draining E2E: test_two_level_chain_observation_to_scoring, test_three_level_chain_observation_to_score_revealed, test_parallel_subscribers_all_complete, test_event_collector_handles_already_captured_events

## Decisions Made
- **Mock sub-pipelines, not CapturePipeline:** CapturePipeline requires hardware (camera, audio, Gemini WebSocket). Testing sub-pipelines directly with shared EventBus catches wiring bugs without hardware dependencies.
- **No ordering assertions between parallel subscribers:** scoring_complete and commentary_delivered are non-deterministic in ordering. Only assert causal ordering (observation_verified before both).
- **Patch asyncio.sleep in scoring pipeline:** Theatrical reveal delays (2s + 1.5s per criterion) would slow tests. Patching at module level keeps tests sub-second while exercising the full reveal flow.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- E2E-01 and E2E-04 requirements fully covered
- Pipeline setup helper and mock patterns ready for reuse in 08-02 (E2E-02 MoE scoring, E2E-03 event wiring regression)
- All 388 tests pass, no regressions

## Self-Check: PASSED

- [x] tests/test_e2e_pipeline_chain.py exists
- [x] tests/test_e2e_task_draining.py exists
- [x] Commit 8cc36d5 exists (Task 1)
- [x] Commit 249b840 exists (Task 2)
- [x] 388/388 tests pass, no regressions

---
*Phase: 08-e2e-pipeline-coverage*
*Completed: 2026-02-17*
