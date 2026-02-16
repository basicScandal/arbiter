---
phase: 03-commentary-output
plan: 03
subsystem: commentary
tags: [gemini, qa-generator, pipeline-orchestrator, event-bus, tts-mute, operator-cli]

# Dependency graph
requires:
  - phase: 03-commentary-output
    plan: 01
    provides: "CommentaryGenerator, Commentary model, PERSONA_PROMPT, QA_PROMPT"
  - phase: 03-commentary-output
    plan: 02
    provides: "TTSEngine with Cartesia WebSocket TTS, DisplayServer with WebSocket broadcast"
  - phase: 02-defense-pipeline
    provides: "SanitizedOutput, ObservationVerified event"
  - phase: 01-capture-layer
    provides: "EventBus, CapturePipeline, OperatorCLI, CaptureConfig, AudioCapture mute/unmute"
provides:
  - "QAGenerator for pointed question generation from SanitizedOutput"
  - "CommentaryPipeline orchestrating generator, TTS, display, and Q&A via event bus"
  - "Full commentary flow: demo stop -> ObservationVerified -> commentary -> TTS + display"
  - "Operator 'qa' command for judge-deferred Q&A question delivery"
  - "TTS mute coordination: audio capture mutes during TTS playback"
affects: [04-scoring-engine, 06-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns: [event-driven-pipeline-orchestration, parallel-sentence-streaming, tts-mute-coordination]

key-files:
  created:
    - src/commentary/qa_generator.py
    - src/commentary/pipeline.py
  modified:
    - src/capture/config.py
    - src/capture/pipeline.py
    - src/operator/cli.py

key-decisions:
  - "QAGenerator uses non-streaming Gemini (short output, no need for streaming)"
  - "CommentaryPipeline reads CARTESIA_API_KEY from env, degrades gracefully if missing"
  - "Neutral emotion for Q&A questions (safe fallback across Cartesia voices)"
  - "Q&A only allowed in stopped state to ensure demo data is available"

patterns-established:
  - "Event-driven pipeline wiring: CommentaryPipeline subscribes to event bus, no direct component coupling"
  - "Graceful degradation: TTS and commentary failures are logged but never crash the pipeline"
  - "Parallel sentence streaming: asyncio.gather for concurrent TTS speak and display push per sentence"

# Metrics
duration: 3min
completed: 2026-02-15
---

# Phase 3 Plan 3: Commentary Pipeline Integration Summary

**QA generator and full commentary pipeline wiring connecting generator, TTS, and display via event bus with operator Q&A command**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-16T07:49:08Z
- **Completed:** 2026-02-16T07:52:02Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Built QAGenerator that produces pointed technical questions from SanitizedOutput via Gemini non-streaming
- Created CommentaryPipeline orchestrator that subscribes to observation_verified and qa_requested events, streaming sentences to TTS and display in parallel
- Integrated commentary pipeline into CapturePipeline with full lifecycle management (setup and cleanup)
- Added TTS mute coordination: audio capture mutes during TTS playback, unmutes when finished
- Added operator 'qa' command that publishes QARequested event for judge deferral

## Task Commits

Each task was committed atomically:

1. **Task 1: Create QA generator and commentary pipeline orchestrator** - `1c6ef9f` (feat)
2. **Task 2: Integrate commentary pipeline into main application with operator QA command** - `be41b0f` (feat)

## Files Created/Modified
- `src/commentary/qa_generator.py` - QAGenerator with Gemini non-streaming generation and fallback questions
- `src/commentary/pipeline.py` - CommentaryPipeline orchestrating generator, TTS, display via event bus
- `src/capture/config.py` - Added cartesia_api_key, cartesia_voice_id, display_host, display_port fields
- `src/capture/pipeline.py` - Wired CommentaryPipeline, added TTS mute coordination handlers
- `src/operator/cli.py` - Added 'qa' command with event bus integration and state validation

## Decisions Made
- QAGenerator uses non-streaming Gemini call (1-2 short questions, no streaming benefit)
- CommentaryPipeline reads CARTESIA_API_KEY from environment, logs warning and degrades gracefully if missing
- Used "neutral" emotion for Q&A questions as safe Cartesia fallback
- Q&A command only allowed in "stopped" state with state-aware hint messages for wrong states

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Cartesia API key and voice ID will be configured at runtime via environment variables.

## Next Phase Readiness
- Full commentary flow complete: demo stop -> observation verified -> commentary generation -> TTS + display delivery
- Operator Q&A command wired and ready for live event use
- Phase 3 (Commentary Output) is now complete -- all 3 plans finished
- Ready for Phase 4 (Scoring Engine) which consumes the same SanitizedOutput

## Self-Check: PASSED

- [x] src/commentary/qa_generator.py - FOUND
- [x] src/commentary/pipeline.py - FOUND
- [x] src/capture/config.py - FOUND
- [x] src/capture/pipeline.py - FOUND
- [x] src/operator/cli.py - FOUND
- [x] Commit 1c6ef9f - FOUND
- [x] Commit be41b0f - FOUND

---
*Phase: 03-commentary-output*
*Completed: 2026-02-15*
