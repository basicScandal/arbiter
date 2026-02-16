# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-15)

**Core value:** Produce fair, defensible scores alongside human judges -- while being entertaining and resistant to prompt injection from a security-savvy audience.
**Current focus:** Phase 2 - Defense Pipeline (IN PROGRESS)

## Current Position

Phase: 2 of 6 (Defense Pipeline)
Plan: 2 of 3 in current phase (COMPLETE)
Status: Plan 02-02 complete, ready for Plan 02-03
Last activity: 2026-02-15 -- Completed 02-02-PLAN.md with roast generator, injection logger, observation sanitizer

Progress: [█████░░░░░] 30%

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: 3min
- Total execution time: 0.33 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-capture-layer | 4/4 | 16min | 4min |
| 02-defense-pipeline | 2/3 | 4min | 2min |

**Recent Trend:**
- Last 5 plans: 01-03 (3min), 01-04 (16min), 02-01 (2min), 02-02 (2min)
- Trend: Stable, fast execution on well-specified plans

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

### Pending Todos

None yet.

### Blockers/Concerns

- Gemini Live API 2-minute session limit needs validation with context window compression (research gap)
- NEBULA:FOG official rubric details needed for Phase 4 scoring calibration

## Session Continuity

Last session: 2026-02-15
Stopped at: Completed 02-02-PLAN.md - Roast generator, injection logger, and observation sanitizer ready for Plan 02-03
Resume file: None
