---
phase: 06-venue-hardening
plan: 01
subsystem: resilience
tags: [tenacity, retry, exponential-backoff, health-tracking, gemini]

# Dependency graph
requires:
  - phase: 03-commentary-output
    provides: "CommentaryGenerator with Gemini streaming calls"
  - phase: 04-scoring-system
    provides: "ScoringEngine with Gemini generate_content calls"
  - phase: 05-memory-deliberation
    provides: "DeliberationEngine with Gemini structured output calls"
provides:
  - "src/resilience/ module with shared retry decorators and health tracker"
  - "GEMINI_RETRY decorator (3 attempts, exponential backoff + jitter)"
  - "GEMINI_RETRY_BACKGROUND decorator (5 attempts, exponential backoff + jitter)"
  - "ServiceHealth class with per-component health tracking and exponential recovery windows"
  - "All Gemini API calls wrapped with tenacity retry before existing fallback logic"
affects: [06-venue-hardening]

# Tech tracking
tech-stack:
  added: [tenacity ~9.0]
  patterns: [tenacity retry decorator composition, exponential backoff with jitter, service health tracking with recovery windows, extract-and-wrap retry pattern]

key-files:
  created:
    - src/resilience/__init__.py
    - src/resilience/retry.py
    - src/resilience/health.py
  modified:
    - pyproject.toml
    - src/scoring/engine.py
    - src/memory/deliberation_engine.py
    - src/commentary/generator.py

key-decisions:
  - "tenacity retry on network exceptions only (ConnectionError, TimeoutError, OSError) -- do NOT retry auth or ValueError"
  - "Extract-and-wrap pattern: private method with retry decorator, public method keeps existing try/except fallback"
  - "3 attempts for interactive paths (commentary), 5 attempts for background paths (scoring, deliberation)"
  - "ServiceHealth exponential recovery window: base * 2^(failures-1) capped at 600s"
  - "Module-level default_health singleton following EventBus pattern"
  - "reraise=True on retry decorators so failures propagate to existing fallback logic"

patterns-established:
  - "Extract-and-wrap: extract API call to private method, decorate with retry, keep outer method fallback intact"
  - "GEMINI_RETRY for interactive paths (3 attempts), GEMINI_RETRY_BACKGROUND for background paths (5 attempts)"
  - "ServiceHealth singleton at module level for shared health tracking"

# Metrics
duration: 2min
completed: 2026-02-16
---

# Phase 6 Plan 1: Retry and Health Foundation Summary

**Tenacity retry decorators with exponential backoff + jitter on all Gemini API calls, plus ServiceHealth tracker with exponential recovery windows**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-16T19:46:54Z
- **Completed:** 2026-02-16T19:49:53Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Installed tenacity ~9.0 and created src/resilience/ module with shared retry configs
- Created ServiceHealth class with per-component health tracking and exponential recovery windows (base * 2^(failures-1), capped at 600s)
- Wrapped all three Gemini-calling modules with tenacity retry decorators using extract-and-wrap pattern
- Existing fallback logic in all modules preserved unchanged -- retries fire before fallback

## Task Commits

Each task was committed atomically:

1. **Task 1: Install tenacity and create resilience module** - `55ef8d4` (feat)
2. **Task 2: Wrap all Gemini API calls with tenacity retry decorators** - `5a7a346` (feat)

## Files Created/Modified
- `src/resilience/__init__.py` - Package init exporting retry configs and ServiceHealth
- `src/resilience/retry.py` - GEMINI_RETRY (3 attempts) and GEMINI_RETRY_BACKGROUND (5 attempts) decorators
- `src/resilience/health.py` - ServiceHealth class with exponential recovery windows + default_health singleton
- `pyproject.toml` - Added tenacity~=9.0 dependency
- `src/commentary/generator.py` - Extracted _stream_gemini with @GEMINI_RETRY
- `src/scoring/engine.py` - Extracted _call_gemini with @GEMINI_RETRY_BACKGROUND
- `src/memory/deliberation_engine.py` - Extracted _call_gemini with @GEMINI_RETRY_BACKGROUND

## Decisions Made
- tenacity retry on network exceptions only (ConnectionError, TimeoutError, OSError) -- auth errors and ValueError are NOT retried
- Extract-and-wrap pattern: private method with retry decorator, public method keeps existing try/except fallback logic intact
- 3 attempts for interactive paths (commentary), 5 attempts for background paths (scoring, deliberation)
- ServiceHealth exponential recovery: base_window * 2^(failures-1) capped at 600 seconds
- Module-level default_health singleton following the EventBus pattern from Phase 1
- reraise=True on both retry decorators so failures propagate to existing fallback logic

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Resilience foundation complete -- all Gemini calls now retry with backoff before falling through to existing fallback logic
- ServiceHealth tracker ready for use by circuit breaker patterns in 06-02
- GEMINI_RETRY and GEMINI_RETRY_BACKGROUND available as decorators for any future Gemini integration points

## Self-Check: PASSED

All 7 files verified present. Both task commits (55ef8d4, 5a7a346) verified in git log.

---
*Phase: 06-venue-hardening*
*Completed: 2026-02-16*
