---
phase: 06-venue-hardening
plan: 02
subsystem: commentary
tags: [tts, fallback, macos-say, cartesia, emotion-map, failover]

# Dependency graph
requires:
  - phase: 03-commentary-output
    provides: TTSEngine with Cartesia WebSocket TTS and emotion-mapped commentary
provides:
  - MacOSSayFallback class for offline TTS via macOS say subprocess
  - TTSEngine automatic failover from Cartesia to macOS say
  - TTSEngine auto-reconnect via _ensure_connected
  - 12-emotion keyword map replacing 3-emotion system
affects: [commentary, tts, display]

# Tech tracking
tech-stack:
  added: [asyncio.create_subprocess_exec, shutil.which]
  patterns: [fallback-chain, auto-reconnect, keyword-emotion-mapping]

key-files:
  created: [src/commentary/tts_fallback.py]
  modified: [src/commentary/tts_engine.py, src/commentary/generator.py]

key-decisions:
  - "MacOSSayFallback always constructed even if say unavailable -- available property gates speak()"
  - "Fallback speak() wraps all errors silently -- fallback must never crash the caller"
  - "TTSFinished always published in finally block on all code paths (Cartesia, fallback, skip)"
  - "Removed 'clearly' from sarcastic keywords to avoid collision with 'clearly the best' (confident)"
  - "_ensure_connected attempts reconnect before each speak, enabling recovery from transient Cartesia failures"

patterns-established:
  - "Fallback chain: primary -> fallback -> silent skip, with coordination events always published"
  - "Auto-reconnect: check connection state, attempt reconnect, degrade if both fail"

# Metrics
duration: 3min
completed: 2026-02-16
---

# Phase 6 Plan 2: TTS Fallback & Emotion Expansion Summary

**macOS say TTS fallback with automatic Cartesia failover and 12-emotion keyword map for varied commentary delivery**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-16T19:46:57Z
- **Completed:** 2026-02-16T19:50:47Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- MacOSSayFallback class speaks text via asyncio subprocess with the macOS say command, always available offline
- TTSEngine automatically falls back to macOS say when Cartesia WebSocket fails, with auto-reconnect attempts
- TTSFinished event always published regardless of which TTS path executes, preserving audio capture mute coordination
- Emotion keyword map expanded from 3 emotions (sarcastic/content/disappointed) to 12 (sarcastic, ironic, contempt, surprised, amazed, disappointed, content, excited, confident, skeptical, curious, proud)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create macOS say TTS fallback and integrate into TTSEngine failover chain** - `f0bff99` (feat)
2. **Task 2: Expand emotion keyword map from 3 to 12+ emotions** - `5a7a346` (feat, pre-applied in 06-01 commit)

## Files Created/Modified
- `src/commentary/tts_fallback.py` - MacOSSayFallback class with async subprocess macOS say speech
- `src/commentary/tts_engine.py` - TTSEngine with failover chain, _ensure_connected, fallback integration
- `src/commentary/generator.py` - 12-emotion _EMOTION_KEYWORDS dict and updated _build_emotion_map method

## Decisions Made
- MacOSSayFallback always constructed in TTSEngine.__init__ even if unavailable -- availability checked at speak time
- Fallback speak() catches all exceptions silently -- the fallback path must never propagate errors
- TTSFinished published in finally blocks on all paths: Cartesia success, Cartesia-to-fallback, and both-unavailable-skip
- Removed "clearly" from sarcastic keywords to prevent collision with "clearly the best" in confident emotion
- _ensure_connected() called at the top of speak() enables automatic recovery from transient Cartesia disconnections

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed "clearly" keyword from sarcastic emotion to fix collision**
- **Found during:** Task 2 (Emotion keyword map expansion)
- **Issue:** "clearly" in sarcastic keywords matched before "clearly the best" in confident, preventing confident emotion from ever triggering
- **Fix:** Removed "clearly" from sarcastic keyword list (6 remaining sarcastic keywords are sufficient)
- **Files modified:** src/commentary/generator.py
- **Verification:** All 12 emotions now reachable in isolation test
- **Committed in:** Pre-applied in 5a7a346

**2. [Overlap] Task 2 changes pre-applied by 06-01 executor**
- **Found during:** Task 2 commit attempt
- **Issue:** The 06-01 plan executor included the emotion keyword changes alongside the retry wrapper changes in generator.py
- **Impact:** No new commit needed for Task 2 -- changes were already correct in HEAD
- **Resolution:** Verified all assertions pass against existing code, documented overlap

---

**Total deviations:** 1 auto-fixed (keyword collision), 1 overlap (pre-applied by 06-01)
**Impact on plan:** Keyword collision fix was necessary for correctness. Pre-applied overlap had no negative impact.

## Issues Encountered
- Task 2 emotion keyword changes and _build_emotion_map update were already committed as part of the 06-01 plan execution (which also modified generator.py for retry wrapping). Verified the pre-applied code was correct and all assertions passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- TTS failover chain complete and tested
- All 12 emotions verified reachable via keyword matching
- TTSFinished coordination preserved across all TTS paths
- Ready for 06-03 (remaining hardening tasks)

## Self-Check: PASSED

- All 4 files verified on disk
- Both commits (f0bff99, 5a7a346) found in git log

---
*Phase: 06-venue-hardening*
*Completed: 2026-02-16*
