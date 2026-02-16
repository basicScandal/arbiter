# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-15)

**Core value:** Produce fair, defensible scores alongside human judges -- while being entertaining and resistant to prompt injection from a security-savvy audience.
**Current focus:** Phase 3 - Commentary Output

## Current Position

Phase: 3 of 6 (Commentary Output)
Plan: 2 of 3 in current phase
Status: Executing Phase 03
Last activity: 2026-02-15 -- Completed 03-02-PLAN.md with TTS engine and display server

Progress: [█████████░] 45%

## Performance Metrics

**Velocity:**
- Total plans completed: 9
- Average duration: 3min
- Total execution time: 0.48 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-capture-layer | 4/4 | 16min | 4min |
| 02-defense-pipeline | 3/3 | 6min | 2min |
| 03-commentary-output | 2/3 | 7min | 3.5min |

**Recent Trend:**
- Last 5 plans: 02-02 (2min), 02-03 (2min), 03-01 (2min), 03-02 (5min)
- Trend: Stable execution, slightly longer on API integration tasks

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Dual-LLM defense layer (Phase 2) must be built before commentary or scoring pipelines
- [Roadmap]: Phases 3 (Commentary) and 4 (Scoring) can execute in parallel after Phase 2
- [Roadmap]: TTS emotional variety and failover deferred to Phase 6 hardening
- [01-01]: Hand-rolled async event bus with asyncio.create_task instead of asyncio-signal-bus library
- [01-01]: Synchronous state machine callbacks publish to async event bus via create_task dispatch
- [01-01]: Module-level default_bus singleton for shared bus across components
- [01-02]: KeyFrameDetector uses cv2.HISTCMP_CORREL with threshold 0.4 for scene change detection
- [01-02]: Camera _capture_and_encode is synchronous, called via asyncio.to_thread for non-blocking capture
- [01-02]: Audio mute discards data but keeps reading the stream to prevent buffer overflow
- [01-03]: Used regular except (not except*) in GeminiSession.run() reconnection loop -- Python disallows break in except* blocks
- [01-03]: OperatorCLI uses asyncio.to_thread(input, ...) for non-blocking stdin reads
- [01-03]: State-aware hints on invalid transitions guide operator to correct command sequence
- [01-04]: Pipeline is thin glue with no business logic -- only component wiring and lifecycle management
- [01-04]: Capture tasks created on demo_started, cancelled on demo_stopped via event bus subscriptions
- [01-04]: Gemini observations stored in demo session on stop for downstream scoring
- [01-04]: Use native audio model (gemini-2.0-flash-exp) with output transcription for text-based observations
- [02-01]: Empty bytes guard in OCR scanner to prevent OpenCV assertion error on empty input
- [02-02]: Whole-observation exclusion over word-level redaction per research anti-pattern guidance
- [02-02]: Roast generation uses gemini-2.0-flash for speed/cost -- short creative text, not complex reasoning
- [02-02]: Fallback roast on any Gemini error to ensure pipeline never blocks on roast generation
- [02-03]: GeminiSession reference passed to DefensePipeline at construction for observation access on demo stop
- [02-03]: Defense pipeline is purely additive -- subscribes to existing events without changing capture behavior
- [02-03]: Pending roast tasks gathered with 5-second timeout on demo stop to avoid blocking
- [03-01]: Gemini 2.5 Flash for commentary generation (fast, already in stack)
- [03-01]: Fresh generate_content_stream per demo with full persona prompt to prevent drift
- [03-01]: Regex sentence splitting on .!? for TTS chunking
- [03-01]: Keyword-based emotion mapping (sarcastic/content/disappointed) for Cartesia TTS
- [03-02]: Used Cartesia websocket_connect (modern API) over deprecated websocket() for proper continue_ support
- [03-02]: Context-per-sentence with no_more_inputs for clean audio streaming lifecycle
- [03-02]: ConnectionManager broadcasts with silent disconnect cleanup for resilient WebSocket delivery
- [03-02]: Uvicorn runs as asyncio.create_task for non-blocking server lifecycle

### Pending Todos

None yet.

### Blockers/Concerns

- Gemini Live API 2-minute session limit needs validation with context window compression (research gap)
- NEBULA:FOG official rubric details needed for Phase 4 scoring calibration

## Session Continuity

Last session: 2026-02-15
Stopped at: Completed 03-02-PLAN.md - TTS engine and display server complete. Ready for 03-03 (commentary pipeline wiring)
Resume file: None
