---
phase: 01-capture-layer
plan: 04
subsystem: capture
tags: [asyncio, pipeline-orchestration, event-driven, lifecycle-management]

# Dependency graph
requires:
  - phase: 01-02
    provides: "CameraCapture and AudioCapture producers with shared queue output"
  - phase: 01-03
    provides: "GeminiSession consumer with Live API streaming and OperatorCLI for demo control"
provides:
  - "CapturePipeline orchestrator wiring camera, audio, Gemini, state machine, and CLI"
  - "main.py entry point that loads config and runs the full capture pipeline"
  - "Complete capture layer: start -> capture -> stop -> reset -> start lifecycle"
affects: [02-defense-pipeline, 03-commentary-engine, 04-scoring-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns: [event-driven-orchestration, task-lifecycle-management, graceful-shutdown]

key-files:
  created:
    - src/capture/pipeline.py
    - src/main.py
  modified: []

key-decisions:
  - "Pipeline is thin glue -- no business logic, only component wiring and lifecycle management"
  - "Capture tasks created on demo_started and cancelled on demo_stopped via event bus subscriptions"
  - "Gemini observations stored in demo session on stop for downstream scoring consumption"

patterns-established:
  - "Pipeline pattern: shared event bus + media queue connect all producers and consumers"
  - "Task lifecycle: create_task on start, stop() + cancel() on stop, with CancelledError handling"
  - "Graceful exit: finally block in run() ensures capture cleanup even if CLI exits unexpectedly"

# Metrics
duration: 1min
completed: 2026-02-15
status: checkpoint-pending
---

# Phase 1 Plan 04: Capture Pipeline Integration Summary

**Pipeline orchestrator wiring camera, audio, Gemini session, state machine, and operator CLI into end-to-end capture system**

## Status: CHECKPOINT PENDING

Task 1 (auto) is complete. Task 2 (checkpoint:human-verify) requires operator verification with live hardware (camera, microphone, Gemini API key).

## Performance

- **Duration:** 1 min (Task 1 only)
- **Started:** 2026-02-16T05:42:52Z
- **Tasks:** 1/2 (checkpoint pending)
- **Files modified:** 2

## Accomplishments
- Built CapturePipeline orchestrator that wires all capture components via shared event bus and media queue
- Pipeline manages full lifecycle: demo_started spins up camera/audio/Gemini tasks, demo_stopped shuts them down gracefully
- Created main.py entry point with dotenv config loading and logging setup
- Graceful shutdown handles both normal exit and interrupted capture sessions

## Task Commits

Each task was committed atomically:

1. **Task 1: Capture pipeline orchestrator and entry point** - `c8e5c68` (feat)
2. **Task 2: End-to-end capture verification** - CHECKPOINT PENDING (human-verify)

## Files Created/Modified
- `src/capture/pipeline.py` - CapturePipeline class: event-driven orchestrator connecting camera, audio, Gemini, state machine, and CLI (174 lines)
- `src/main.py` - Entry point: dotenv loading, logging config, pipeline creation and execution (34 lines)

## Decisions Made
- Pipeline is intentionally thin glue with no business logic -- it only wires components and manages their lifecycle via event bus subscriptions
- Capture tasks (camera, audio, gemini) are created as named asyncio.Tasks for better debugging visibility
- Demo summary (key frames, transcripts, observations count) is printed to stdout on demo stop for operator feedback

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
**GEMINI_API_KEY is required for end-to-end verification.** The operator must:
1. Copy `.env.example` to `.env`
2. Add their Gemini API key: `GEMINI_API_KEY=your-key`
3. Ensure camera and microphone hardware are available

## Checkpoint: End-to-End Verification

The operator must verify the full capture system with live hardware:
- Run `uv run python -m src.main`
- Test full lifecycle: start -> capture -> stop -> reset -> start again
- Verify camera frames, audio transcription, Gemini observations appear in real-time
- Verify error handling on invalid commands

## Next Phase Readiness
- Capture layer code is complete pending hardware verification
- All components are wired and importable
- Phase 2 (defense pipeline) can begin design/planning in parallel

## Self-Check: PASSED

All 2 created files verified on disk. Task 1 commit (c8e5c68) verified in git log. Line counts: pipeline.py=174 (min 60), main.py=34 (min 20).

---
*Phase: 01-capture-layer*
*Completed: 2026-02-15 (pending checkpoint)*
