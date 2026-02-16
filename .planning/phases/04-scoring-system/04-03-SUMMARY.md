---
phase: 04-scoring-system
plan: 03
subsystem: scoring
tags: [json-persistence, event-bus, scoring-pipeline, operator-cli, theatrical-reveal, asyncio]

# Dependency graph
requires:
  - phase: 04-scoring-system
    provides: ScoringEngine with isolated Gemini client (04-01), DisplayServer score push methods (04-02)
  - phase: 03-commentary-output
    provides: CommentaryDelivered event, DisplayServer, CommentaryPipeline
  - phase: 02-defense-pipeline
    provides: ObservationVerified event with SanitizedOutput
  - phase: 01-capture-layer
    provides: EventBus, CapturePipeline, OperatorCLI, DemoMachine
provides:
  - ScoreStore with JSON file persistence per team (data/scores/*.json)
  - ScoringPipeline orchestrator wiring engine, store, display, and event bus
  - Operator CLI track assignment (start TeamName SHADOW::VECTOR)
  - Full scoring event flow integrated into CapturePipeline
affects: [05-deliberation]

# Tech tracking
tech-stack:
  added: []
  patterns: [event-sequenced-reveal, detached-asyncio-task-for-display, shared-display-server-instance, pending-scorecard-bridge]

key-files:
  created:
    - src/scoring/store.py
    - src/scoring/pipeline.py
  modified:
    - src/operator/cli.py
    - src/capture/pipeline.py

key-decisions:
  - "Detached asyncio.create_task for score reveal -- must NOT block event bus callback"
  - "Shared DisplayServer instance between commentary and scoring (isolation is LLM path, not display)"
  - "Default track ROGUE::AGENT when operator does not specify a track"
  - "Pending scorecards dict bridges timing gap between scoring completion and commentary delivery"

patterns-established:
  - "Event sequencing: score on observation_verified, reveal on commentary_delivered"
  - "Detached display tasks: asyncio.create_task for theatrical sequences that must not block event bus"
  - "Shared infrastructure: DisplayServer is shared, LLM clients are isolated"

# Metrics
duration: 3min
completed: 2026-02-16
---

# Phase 4 Plan 3: Scoring Pipeline Integration Summary

**End-to-end scoring pipeline with JSON persistence, event-sequenced theatrical reveal after commentary, and operator track assignment via CLI**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-16T18:10:55Z
- **Completed:** 2026-02-16T18:14:29Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- ScoreStore persists DemoScorecards as human-readable JSON files per team with filesystem-safe naming
- ScoringPipeline orchestrator sequences scoring after observation_verified and reveals after commentary_delivered
- Theatrical score reveal with dramatic timing (2s intro, 1.5s per criterion, 1s before total) runs as detached asyncio task
- Operator CLI accepts optional track argument: `start TeamName SHADOW::VECTOR`
- Full scoring pipeline wired into CapturePipeline sharing the commentary DisplayServer instance

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ScoreStore for JSON file persistence** - `20f92ac` (feat)
2. **Task 2: Create ScoringPipeline orchestrator with theatrical reveal** - `03223eb` (feat)
3. **Task 3: Add track to operator CLI and wire scoring into main pipeline** - `bc27018` (feat)

## Files Created/Modified
- `src/scoring/store.py` - ScoreStore with save/load/load_all methods, team name sanitization, asyncio.to_thread file I/O
- `src/scoring/pipeline.py` - ScoringPipeline subscribing to observation_verified and commentary_delivered, theatrical reveal via create_task
- `src/operator/cli.py` - Updated start command with optional track argument, new score command, track validation against VALID_TRACKS set
- `src/capture/pipeline.py` - ScoringPipeline created with shared DisplayServer, setup wired in run(), scoring_pipeline passed to OperatorCLI

## Decisions Made
- Detached asyncio.create_task for score reveal ensures the display sequence never blocks the event bus callback chain
- Commentary and scoring share the same DisplayServer instance -- the SCORE-03 isolation requirement applies to the LLM path (separate genai.Client), not the display path
- Default track is ROGUE::AGENT (the "novel/uncategorized" track) when operator does not specify one
- Pending scorecards dictionary bridges the timing gap between scoring (triggered by observation_verified) and reveal (triggered by commentary_delivered)
- TYPE_CHECKING import for ScoringPipeline in cli.py avoids circular import issues

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full scoring system complete: models, engine, rubric, display, store, pipeline, CLI integration
- Phase 4 (Scoring System) is now complete with all 3 plans finished
- ScoreStore persists JSON files to data/scores/ directory, ready for Phase 5 deliberation consumption
- ScoringPipeline publishes ScoringComplete and ScoreRevealed events for downstream phases
- Full event flow operational: demo_stopped -> observation_verified -> scoring + commentary (parallel) -> commentary_delivered -> score reveal

## Self-Check: PASSED

All created files verified on disk. All commit hashes (20f92ac, 03223eb, bc27018) found in git log.

---
*Phase: 04-scoring-system*
*Completed: 2026-02-16*
