---
phase: 07-test-infrastructure
plan: 01
subsystem: testing
tags: [pytest, pytest-timeout, pytest-xdist, vcrpy, asyncio, fixtures, singleton-reset, event-collector]

# Dependency graph
requires:
  - phase: 02-capture-layer
    provides: "EventBus, CaptureEvent models, default_bus singleton"
  - phase: 03-resilience
    provides: "ServiceHealth default_health singleton, GeminiRateLimiter singleton"
provides:
  - "Autouse singleton reset fixture preventing state leakage between tests"
  - "EventCollector helper for deterministic async event assertions"
  - "pytest timeout guards (30s) killing hanging tests"
  - "integration and slow test markers for selective test runs"
  - "VCR config fixture for HTTP cassette recording/playback"
  - "asyncio_mode=auto eliminating need for @pytest.mark.asyncio markers"
affects: [07-02, 08-test-coverage, 09-groq-rehearsal, 10-dashboard-hardening]

# Tech tracking
tech-stack:
  added: [pytest-timeout, pytest-xdist, vcrpy, pytest-recording]
  patterns: [in-place-singleton-reset, event-collector-wait-for, autouse-fixture]

key-files:
  created:
    - tests/conftest.py
    - tests/helpers/__init__.py
    - tests/helpers/event_collector.py
  modified:
    - pyproject.toml

key-decisions:
  - "In-place singleton reset over object replacement to handle import-time name bindings"
  - "asyncio_mode=auto to eliminate @pytest.mark.asyncio boilerplate"
  - "thread timeout method for xdist/thread compatibility"

patterns-established:
  - "In-place singleton reset: clear dict state on original objects, restore module attributes to canonical instances"
  - "EventCollector wait_for(): register asyncio.Event waiter, await with timeout, no sleep-based polling"
  - "VCR config fixture: filter sensitive headers, cassette_library_dir=tests/cassettes"

# Metrics
duration: 10min
completed: 2026-02-17
---

# Phase 7 Plan 1: Test Infrastructure Summary

**pytest infrastructure with timeout guards, in-place singleton reset fixtures, and deterministic EventCollector helper for async assertions**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-17T09:40:06Z
- **Completed:** 2026-02-17T09:51:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Installed pytest-timeout, pytest-xdist, vcrpy, pytest-recording as dev dependencies
- Configured pytest with asyncio_mode=auto, 30s timeout, integration/slow markers, fail-fast addopts
- Built autouse singleton reset fixture clearing EventBus, ServiceHealth, and GeminiRateLimiter between every test
- Created EventCollector helper with deterministic wait_for() method replacing sleep-based polling
- Fixed pre-existing test ordering bug in test_qa.py exposed by singleton reset

## Task Commits

Each task was committed atomically:

1. **Task 1: Add dev dependencies and configure pytest** - `a4fb14a` (chore)
2. **Task 2: Create EventCollector helper and conftest.py** - `7852b28` (feat)
3. **Task 2 fix: In-place singleton reset** - `64070c7` (fix)
4. **Task 3: Validate full test suite** - validation only, no commit needed

## Files Created/Modified
- `pyproject.toml` - Added 4 dev deps (pytest-timeout, pytest-xdist, vcrpy, pytest-recording) and [tool.pytest.ini_options] config
- `tests/conftest.py` - Autouse _reset_singletons fixture, event_bus/event_collector/vcr_config fixtures
- `tests/helpers/__init__.py` - Package marker for test helpers
- `tests/helpers/event_collector.py` - EventCollector class with subscribe_all, wait_for(), of_type(), count()

## Decisions Made
- **In-place singleton reset over object replacement:** Modules like pipeline.py do `from src.resilience.health import default_health` at import time, creating direct name bindings to the original object. Replacing the module attribute with a new object leaves these stale. Instead, we clear state on the original objects and restore module attributes to the canonical instances.
- **asyncio_mode=auto:** Eliminates need for `@pytest.mark.asyncio` on every async test. Existing markers become harmless no-ops.
- **thread timeout method:** Required for compatibility with pytest-xdist workers and threaded tests (signal method only works in main thread).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing test ordering bug in test_qa.py**
- **Found during:** Task 3 (full suite validation)
- **Issue:** `TestPipelineTTSHealthy.test_tts_and_display_called_in_parallel` failed when run after `TestPipelineDelivery` tests. Pipeline.py holds an import-time reference to `default_health`. Previous tests marked cartesia_tts unhealthy on that reference. The original plan's approach (replacing module attribute with new ServiceHealth) didn't affect pipeline.py's stale binding.
- **Fix:** Changed singleton reset strategy to clear state in-place on the original objects rather than replacing them. Captured original references at conftest import time. All modules share the same canonical object.
- **Files modified:** tests/conftest.py
- **Verification:** Full test suite (371 tests) passes twice consecutively with identical results
- **Committed in:** `64070c7`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix for correctness of the singleton reset approach. The in-place strategy is more robust than the replacement strategy specified in the plan. No scope creep.

## Issues Encountered
- The plan specified replacing module-level singletons with new objects, but this fails for modules that import singletons at module load time (binding to the original object). Switched to in-place state clearing which handles both import-time and call-time access patterns.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 371 existing tests pass with new infrastructure active
- EventCollector ready for use in upcoming integration/E2E test plans
- Marker infrastructure ready: `pytest -m integration` and `pytest -m "not integration"` work correctly
- VCR config fixture ready for HTTP cassette tests
- Timeout guards active: any hanging test killed at 30s

## Self-Check: PASSED

All files verified present. All commit hashes found in git log.

---
*Phase: 07-test-infrastructure*
*Completed: 2026-02-17*
