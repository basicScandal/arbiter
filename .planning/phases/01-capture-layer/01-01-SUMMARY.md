---
phase: 01-capture-layer
plan: 01
subsystem: capture
tags: [pydantic, python-statemachine, asyncio, event-bus, python-dotenv]

# Dependency graph
requires:
  - phase: none
    provides: "First plan -- no prior dependencies"
provides:
  - "Pydantic data models for capture events (MediaChunk, FrameData, TranscriptSegment, DemoSession, CaptureEvent)"
  - "Typed event subclasses (DemoStarted, DemoStopped, FrameCaptured, KeyFrameDetected, TranscriptReceived)"
  - "CaptureConfig with env var loading and sensible defaults"
  - "Async EventBus with subscribe/publish/subscribe_all and error isolation"
  - "DemoMachine state machine (idle -> capturing -> stopped -> idle) with event publishing"
affects: [01-02-PLAN, 01-03-PLAN, 01-04-PLAN, 02-defense-pipeline]

# Tech tracking
tech-stack:
  added: [google-genai, opencv-python, pyaudio, python-statemachine, pydantic, pillow, numpy, python-dotenv]
  patterns: [async-event-bus, state-machine-lifecycle, pydantic-models, env-config]

key-files:
  created:
    - pyproject.toml
    - .env.example
    - src/__init__.py
    - src/capture/__init__.py
    - src/capture/models.py
    - src/capture/config.py
    - src/capture/event_bus.py
    - src/capture/demo_machine.py
    - .gitignore
  modified: []

key-decisions:
  - "Hand-rolled async event bus with asyncio.create_task instead of asyncio-signal-bus library for simplicity"
  - "Synchronous state machine callbacks that publish to async event bus (python-statemachine on_enter hooks are sync, bus dispatches async)"
  - "Module-level default_bus singleton for convenience imports"

patterns-established:
  - "EventBus pattern: subscribe by event_type string, publish dispatches via asyncio.create_task, errors logged but never propagated"
  - "DemoMachine pattern: state transitions publish typed events, constructor accepts optional event_bus parameter"
  - "CaptureEvent hierarchy: base class with event_type/timestamp/payload, subclasses add specific fields with default event_type"
  - "Config loading: CaptureConfig Pydantic model + load_config() reads from env via python-dotenv"

# Metrics
duration: 4min
completed: 2026-02-15
---

# Phase 1 Plan 01: Project Scaffolding Summary

**Python project with Pydantic capture models, async event bus, and demo lifecycle state machine using python-statemachine**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-16T05:29:48Z
- **Completed:** 2026-02-16T05:34:13Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Scaffolded Python project with all capture layer dependencies installable via `uv sync`
- Built typed Pydantic data models for the entire capture event system (7 model classes)
- Implemented async EventBus with non-blocking publish, error isolation, and global subscriber support
- Built DemoMachine state machine with idle/capturing/stopped lifecycle that publishes events on transitions

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffolding, dependencies, and data models** - `57607d7` (feat)
2. **Task 2: Async event bus and demo lifecycle state machine** - `530353d` (feat)

## Files Created/Modified
- `pyproject.toml` - Project metadata, dependencies (google-genai, opencv-python, pyaudio, etc.), ruff config
- `.env.example` - Documented environment variables for capture configuration
- `.gitignore` - Python/venv/IDE/OS ignore patterns
- `src/__init__.py` - Package init
- `src/capture/__init__.py` - Capture subpackage init
- `src/capture/models.py` - Pydantic models: MediaChunk, FrameData, TranscriptSegment, DemoSession, CaptureEvent, DemoStarted, DemoStopped, FrameCaptured, KeyFrameDetected, TranscriptReceived
- `src/capture/config.py` - CaptureConfig model with load_config() env var loader
- `src/capture/event_bus.py` - Async EventBus with subscribe/unsubscribe/publish/subscribe_all
- `src/capture/demo_machine.py` - DemoMachine state machine with lifecycle event publishing

## Decisions Made
- Used hand-rolled async event bus with `asyncio.create_task()` instead of asyncio-signal-bus library, as recommended in research doc -- simpler, no extra dependency
- State machine on_enter callbacks are synchronous (python-statemachine 2.6 default) but publish to the async event bus which dispatches callbacks via `asyncio.create_task()`
- Created module-level `default_bus` singleton so components can import and use a shared bus without explicit wiring
- Used `hatchling` as build backend with explicit `packages = ["src"]` for proper editable installs
- Pinned dependency versions with `~=` (compatible release) to match research recommendations while allowing patch updates

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed hatchling build backend path**
- **Found during:** Task 1 (uv sync)
- **Issue:** Used `hatchling.backends` instead of `hatchling.build` as build-backend
- **Fix:** Corrected to `hatchling.build`
- **Files modified:** pyproject.toml
- **Verification:** uv sync completed successfully
- **Committed in:** 57607d7 (Task 1 commit)

**2. [Rule 3 - Blocking] Installed portaudio system dependency**
- **Found during:** Task 1 (uv sync)
- **Issue:** PyAudio requires portaudio C library headers which were not installed
- **Fix:** Ran `brew install portaudio`
- **Files modified:** System-level (homebrew)
- **Verification:** uv sync completed, pyaudio built successfully
- **Committed in:** 57607d7 (Task 1 commit)

**3. [Rule 3 - Blocking] Added hatchling packages config for src layout**
- **Found during:** Task 1 (uv sync)
- **Issue:** Hatchling couldn't find package named "arbiter" -- project uses `src/` layout
- **Fix:** Added `[tool.hatch.build.targets.wheel] packages = ["src"]` to pyproject.toml
- **Files modified:** pyproject.toml
- **Verification:** uv sync completed, editable install succeeded
- **Committed in:** 57607d7 (Task 1 commit)

**4. [Rule 2 - Missing Critical] Added .gitignore**
- **Found during:** Post-task verification
- **Issue:** No .gitignore present, __pycache__ and .venv would be committed
- **Fix:** Created .gitignore with Python, venv, IDE, and OS patterns
- **Files modified:** .gitignore
- **Verification:** git status no longer shows __pycache__ directories
- **Committed in:** (will be in metadata commit)

---

**Total deviations:** 4 auto-fixed (1 bug, 2 blocking, 1 missing critical)
**Impact on plan:** All auto-fixes necessary for correct build and clean repo. No scope creep.

## Issues Encountered
- Dependency version pins in plan (`google-genai~=1.63`, `opencv-python~=4.13`) were higher than latest available versions on PyPI. Adjusted to `~=1.13` and `~=4.11` respectively. google-genai resolved to 1.63.0 (the `~=1.13` constraint was compatible). opencv-python resolved to 4.13.0.92.

## User Setup Required
None - no external service configuration required. GEMINI_API_KEY will be needed in later plans when Gemini sessions are established.

## Next Phase Readiness
- All foundational modules (models, config, event bus, state machine) are ready for Plan 02 (camera/audio capture)
- Plan 02 will import FrameData, MediaChunk, EventBus, DemoMachine directly
- Plan 03 will use CaptureConfig for Gemini session configuration
- No blockers for next plan

## Self-Check: PASSED

All 9 created files verified on disk. Both task commits (57607d7, 530353d) verified in git log.

---
*Phase: 01-capture-layer*
*Completed: 2026-02-15*
