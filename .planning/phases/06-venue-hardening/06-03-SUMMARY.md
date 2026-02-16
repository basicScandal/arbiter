---
phase: 06-venue-hardening
plan: 03
subsystem: capture
tags: [state-machine, pause-resume, degraded-mode, tts-health, service-health, operator-controls]

# Dependency graph
requires:
  - phase: 01-capture-layer
    provides: "DemoMachine state machine, AudioCapture mute/unmute, CameraCapture"
  - phase: 03-commentary-output
    provides: "CommentaryPipeline with TTS speak and display push"
  - phase: 06-venue-hardening
    provides: "ServiceHealth with exponential recovery windows, TTSEngine failover chain"
provides:
  - "DemoMachine paused state with pause_demo/resume_demo transitions"
  - "DemoPaused and DemoResumed event types"
  - "Operator pause/resume via CLI commands and TUI keybindings (Ctrl+P, Ctrl+O)"
  - "Capture pipeline pause/resume handlers (audio mute, camera frame discard)"
  - "Commentary pipeline text-only degradation when TTS is unhealthy"
affects: [venue-hardening, operator-controls, capture, commentary]

# Tech tracking
tech-stack:
  added: []
  patterns: [pause-resume state machine, camera frame discard on pause, ServiceHealth-gated TTS delivery, text-only degradation path]

key-files:
  created: []
  modified:
    - src/capture/models.py
    - src/capture/demo_machine.py
    - src/operator/cli.py
    - src/operator/tui.py
    - src/capture/camera.py
    - src/capture/pipeline.py
    - src/commentary/pipeline.py

key-decisions:
  - "Camera pause discards frames but keeps device open (cv2.VideoCapture stays alive)"
  - "on_exit_paused only publishes DemoResumed when target is capturing, not stopped"
  - "ServiceHealth is_healthy checked per-sentence before TTS speak, not once per commentary"
  - "Display server always receives text regardless of TTS health (text-only degradation)"

patterns-established:
  - "Camera pause/resume: _paused flag with frame discard in capture loop (mirrors audio mute pattern)"
  - "Health-gated delivery: check is_healthy before expensive service call, degrade to simpler path"

# Metrics
duration: 5min
completed: 2026-02-16
---

# Phase 6 Plan 3: Pause/Resume Controls & Text-Only Degradation Summary

**DemoMachine paused state with operator CLI/TUI controls, capture suspension via audio mute and camera frame discard, and ServiceHealth-gated text-only commentary when TTS is unhealthy**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-16T19:53:46Z
- **Completed:** 2026-02-16T19:59:21Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Extended DemoMachine with paused state, pause_demo/resume_demo transitions, and stop_demo from both capturing and paused states
- Operator can pause/resume via CLI commands with state-aware hints and TUI keybindings (Ctrl+P pause, Ctrl+O resume) with PAUSED header display
- Capture pipeline suspends audio (mute) and camera (frame discard, device stays open) on demo pause, resumes both on demo resume
- Commentary pipeline checks ServiceHealth before each TTS speak and degrades to text-only display when TTS is unhealthy

## Task Commits

Each task was committed atomically:

1. **Task 1: Add paused state to DemoMachine with event types and operator controls** - `77e97e8` (feat)
2. **Task 2: Wire pause/resume into capture pipeline and add degraded-mode text-only commentary** - `0efa252` (feat)

## Files Created/Modified
- `src/capture/models.py` - DemoPaused and DemoResumed event types
- `src/capture/demo_machine.py` - Paused state with pause_demo/resume_demo/stop_demo transitions
- `src/operator/cli.py` - Pause/resume commands with state-aware hints
- `src/operator/tui.py` - Ctrl+P/Ctrl+O keybindings, PAUSED header state, pause/resume command dispatch
- `src/capture/camera.py` - Camera pause/resume with _paused flag and frame discard loop
- `src/capture/pipeline.py` - Pause/resume event handlers (audio mute, camera pause)
- `src/commentary/pipeline.py` - ServiceHealth-gated TTS with text-only degradation path

## Decisions Made
- Camera pause discards frames but keeps cv2.VideoCapture device open -- prevents expensive device reopen on resume
- on_exit_paused callback only publishes DemoResumed when transitioning to capturing, not when stopping from paused (avoids false resume event)
- ServiceHealth is checked per-sentence before TTS speak, not once per commentary block -- allows recovery mid-delivery
- Display server always receives text regardless of TTS health state -- audience sees commentary even if they cannot hear it (REL-02 satisfaction)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added camera pause/resume methods to CameraCapture**
- **Found during:** Task 2 (Capture pipeline pause/resume handlers)
- **Issue:** CameraCapture had no pause/resume API; pipeline handler needed to suspend camera frames
- **Fix:** Added _paused flag, pause()/resume() methods, and frame discard in capture loop (mirrors AudioCapture mute pattern)
- **Files modified:** src/capture/camera.py
- **Verification:** Camera import succeeds, pause/resume methods available
- **Committed in:** 0efa252 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (blocking issue)
**Impact on plan:** Camera pause was anticipated as a possibility in the plan ("or set a _paused flag if camera does not have pause"). No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 6 (Venue Hardening) is now COMPLETE -- all 3 plans executed
- All hardening features in place: retry with backoff, TTS failover, pause/resume controls, text-only degradation
- System is venue-ready with operator controls for handling technical difficulties

## Self-Check: PASSED

All 7 files verified present. Both task commits (77e97e8, 0efa252) verified in git log.

---
*Phase: 06-venue-hardening*
*Completed: 2026-02-16*
