---
phase: 09-groq-fallback-rehearsal-mode
plan: 02
subsystem: testing
tags: [rehearsal, synthetic-data, mock, event-bus, dry-run, cli]

# Dependency graph
requires:
  - phase: 08-e2e-pipeline-coverage
    provides: E2E pipeline chain test patterns (mock wiring approach)
provides:
  - "Rehearsal mode: full dry-run system with synthetic events and canned LLM responses"
  - "ReplayProvider: LLMProvider returning deterministic canned responses"
  - "SyntheticCapture: mock event injection without hardware"
  - "--rehearsal CLI flag for zero-dependency demo rehearsal"
  - "Dashboard rehearsal action for operator-triggered dry runs"
affects: [10-dashboard-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ReplayProvider pattern: LLMProvider subclass with keyword-based canned response routing"
    - "SyntheticCapture pattern: event bus injection with minimal valid data (1x1 JPEG, realistic transcripts)"
    - "RehearsalPipeline pattern: production pipeline wiring with mock I/O components"

key-files:
  created:
    - src/rehearsal/__init__.py
    - src/rehearsal/replay_provider.py
    - src/rehearsal/synthetic_capture.py
    - src/rehearsal/rehearsal_pipeline.py
  modified:
    - src/main.py
    - src/operator/web.py

key-decisions:
  - "ReplayProvider canned scoring JSON uses realistic varied scores (8.5/7.0/6.5) not uniform 5.0 -- validates MoE scoring path end-to-end"
  - "Rehearsal --rehearsal flag placed before load_dotenv() -- no .env or API keys required at all"
  - "RehearsalPipeline accepts optional display parameter -- dashboard can share production DisplayServer while CLI uses MagicMock"
  - "Scoring pipeline sleep patched to 0.1s max in rehearsal -- fast enough to verify flow without theatrical delays"

patterns-established:
  - "Rehearsal mode pattern: same event bus subscriptions as production, different I/O backends"
  - "Mock component assembly: follow E2E test patterns (MagicMock with AsyncMock methods) for pipeline mocking"

# Metrics
duration: 6min
completed: 2026-02-17
---

# Phase 9 Plan 2: Rehearsal Mode Summary

**Full dry-run system with SyntheticCapture, ReplayProvider, and RehearsalPipeline exercising defense/commentary/scoring/deliberation via event bus without hardware or API keys**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-17T18:01:29Z
- **Completed:** 2026-02-17T18:08:17Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- ReplayProvider returns valid scoring JSON that parses through ScoringEngine._parse_and_validate (8.2 total with track bonus)
- Full pipeline chain fires in rehearsal: defense -> commentary -> scoring (MoE) -> deliberation memory save
- `python -m arbiter --rehearsal` runs complete demo cycle with zero external dependencies
- Dashboard "rehearsal" action passes DisplayServer for live operator visibility

## Task Commits

Each task was committed atomically:

1. **Task 1: Create rehearsal module with SyntheticCapture, ReplayProvider, and RehearsalPipeline** - `3be1951` (feat)
2. **Task 2: Wire --rehearsal CLI flag and dashboard rehearsal action** - `9d4da07` (feat)

## Files Created/Modified
- `src/rehearsal/__init__.py` - Public API exports for rehearsal module
- `src/rehearsal/replay_provider.py` - LLMProvider subclass returning canned scoring/commentary/deliberation/Q&A responses
- `src/rehearsal/synthetic_capture.py` - Publishes DemoStarted/KeyFrameDetected x3/TranscriptReceived x3/DemoStopped to event bus
- `src/rehearsal/rehearsal_pipeline.py` - Orchestrates all 4 sub-pipelines with mock GeminiSession, TTS, display, and ReplayProvider
- `src/main.py` - Added --rehearsal flag with early return before load_dotenv()
- `src/operator/web.py` - Added "rehearsal" action to WebOperator._handle_command

## Decisions Made
- ReplayProvider canned scoring JSON uses realistic varied scores (8.5/7.0/6.5) not uniform 5.0 -- validates MoE scoring path end-to-end
- Rehearsal --rehearsal flag placed before load_dotenv() -- no .env or API keys required at all
- RehearsalPipeline accepts optional display parameter -- dashboard can share production DisplayServer while CLI uses MagicMock
- Scoring pipeline asyncio.sleep patched to 0.1s max in rehearsal -- fast enough to verify flow without 5+ second theatrical delays
- Deliberation memory store mocked with AsyncMock to avoid writing to production data dirs

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. Rehearsal mode is fully self-contained.

## Next Phase Readiness
- Phase 9 complete (both plans: Groq fallback + rehearsal mode)
- Ready for Phase 10: Dashboard Hardening
- Rehearsal mode provides operators a way to verify the full system before live events

## Self-Check: PASSED

All 4 created files verified present. Both task commits (3be1951, 9d4da07) verified in git log. 388 existing tests pass.

---
*Phase: 09-groq-fallback-rehearsal-mode*
*Completed: 2026-02-17*
