---
phase: 03-commentary-output
plan: 02
subsystem: commentary
tags: [cartesia, pyaudio, tts, fastapi, websocket, uvicorn, jinja2, display]

# Dependency graph
requires:
  - phase: 03-commentary-output
    plan: 01
    provides: "TTSSpeaking, TTSFinished event types and Commentary model with emotion_map"
  - phase: 01-capture-layer
    provides: "EventBus for publish/subscribe coordination"
provides:
  - "TTSEngine with async Cartesia WebSocket TTS streaming and PyAudio playback"
  - "DisplayServer with FastAPI WebSocket broadcast for audience text display"
  - "HTML template for dark-themed large-screen projection display"
affects: [03-03, 04-scoring-engine]

# Tech tracking
tech-stack:
  added: []
  patterns: [cartesia-websocket-context, pyaudio-float32-streaming, fastapi-websocket-broadcast, connection-manager]

key-files:
  created:
    - src/commentary/tts_engine.py
    - src/commentary/display_server.py
    - src/commentary/templates/display.html
  modified: []

key-decisions:
  - "Used Cartesia websocket_connect (modern API) over deprecated websocket() for proper continue_ support"
  - "Context-per-sentence with no_more_inputs for clean audio streaming lifecycle"
  - "ConnectionManager broadcasts with silent disconnect cleanup for resilient WebSocket delivery"
  - "Uvicorn runs as asyncio.create_task for non-blocking server lifecycle"

patterns-established:
  - "TTSFinished always published in finally block: Never leave capture muted on TTS failure"
  - "ConnectionManager pattern: Broadcast to all, silently remove disconnected clients"
  - "Auto-reconnecting WebSocket client in display HTML with exponential backoff"

# Metrics
duration: 5min
completed: 2026-02-15
---

# Phase 3 Plan 2: TTS Engine and Display Server Summary

**Cartesia WebSocket TTS engine with per-sentence emotion control and FastAPI WebSocket display server for audience projection**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-16T07:41:14Z
- **Completed:** 2026-02-16T07:46:32Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Built TTSEngine with async Cartesia WebSocket streaming, PyAudio float32 playback, and per-sentence emotion control
- Built DisplayServer with FastAPI, uvicorn as async background task, and WebSocket broadcast via ConnectionManager
- Created dark-themed HTML display template (48px font, auto-reconnecting WebSocket, fade-in animations) for NEBULA:FOG 2026 projection

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Cartesia TTS engine with emotion control and audio playback** - `d7ecfbf` (feat)
2. **Task 2: Create FastAPI display server with WebSocket broadcast and HTML template** - `d39632d` (feat)

## Files Created/Modified
- `src/commentary/tts_engine.py` - TTSEngine with Cartesia WebSocket TTS, PyAudio playback, and event bus integration
- `src/commentary/display_server.py` - DisplayServer with FastAPI, ConnectionManager, and uvicorn async task
- `src/commentary/templates/display.html` - Audience display with dark theme, large font, auto-reconnecting WebSocket

## Decisions Made
- Used Cartesia `websocket_connect()` (modern API) instead of deprecated `websocket()` -- the deprecated method hardcodes `continue_=False`, preventing proper sentence continuation
- Context-per-sentence approach with `no_more_inputs()` for clean audio streaming lifecycle
- ConnectionManager silently removes disconnected clients during broadcast to prevent error propagation
- Uvicorn server runs as `asyncio.create_task` so it never blocks the main event loop

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used modern Cartesia websocket_connect API instead of deprecated websocket()**
- **Found during:** Task 1 (TTS engine implementation)
- **Issue:** Plan specified `self._ws = await self._client.tts.websocket()` but the deprecated `websocket()` method's backcompat wrapper hardcodes `continue_=False` in `ctx.send()`, making sentence continuation impossible
- **Fix:** Used `self._client.tts.websocket_connect().enter()` which returns `AsyncTTSResourceConnection` with proper `context()` API supporting `continue_` parameter
- **Files modified:** src/commentary/tts_engine.py
- **Verification:** Import succeeds, all methods present
- **Committed in:** d7ecfbf (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** API adaptation necessary for correct continuation behavior. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Cartesia API key will be needed at runtime (configured in Phase 6 hardening).

## Next Phase Readiness
- TTSEngine ready for pipeline wiring in Plan 03 (commentary pipeline integration)
- DisplayServer ready for pipeline wiring in Plan 03
- Event bus integration (TTSSpeaking/TTSFinished) ready for capture mute coordination
- HTML template ready for audience-facing display at competition

## Self-Check: PASSED

- [x] src/commentary/tts_engine.py - FOUND
- [x] src/commentary/display_server.py - FOUND
- [x] src/commentary/templates/display.html - FOUND
- [x] Commit d7ecfbf - FOUND
- [x] Commit d39632d - FOUND

---
*Phase: 03-commentary-output*
*Completed: 2026-02-15*
