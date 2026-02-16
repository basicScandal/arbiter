# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-15)

**Core value:** Produce fair, defensible scores alongside human judges -- while being entertaining and resistant to prompt injection from a security-savvy audience.
**Current focus:** Phase 5 Complete - Memory and Deliberation. Ready for Phase 6 Hardening.

## Current Position

Phase: 5 of 6 (Memory & Deliberation) -- COMPLETE
Plan: 3 of 3 in current phase (05-03 complete)
Status: Phase 05 Complete
Last activity: 2026-02-16 -- Completed 05-03-PLAN.md with deliberation pipeline integration

Progress: [████████████████░] 94%

## Performance Metrics

**Velocity:**
- Total plans completed: 16
- Average duration: 3min
- Total execution time: 0.79 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-capture-layer | 4/4 | 16min | 4min |
| 02-defense-pipeline | 3/3 | 6min | 2min |
| 03-commentary-output | 3/3 | 10min | 3.3min |
| 04-scoring-system | 3/3 | 8min | 2.7min |
| 05-memory-deliberation | 3/3 | 8min | 2.7min |

**Recent Trend:**
- Last 5 plans: 04-02 (2min), 04-03 (3min), 05-01 (2min), 05-02 (2min), 05-03 (4min)
- Trend: Stable execution at ~2-4min/plan

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
- [03-03]: QAGenerator uses non-streaming Gemini (short output, no need for streaming)
- [03-03]: CommentaryPipeline reads CARTESIA_API_KEY from env, degrades gracefully if missing
- [03-03]: Neutral emotion for Q&A questions (safe fallback across Cartesia voices)
- [03-03]: Q&A only allowed in stopped state to ensure demo data is available
- [04-01]: Separate genai.Client instance for scoring (SCORE-03 isolation from commentary P-LLM)
- [04-01]: Python-computed weighted totals, never trust LLM arithmetic
- [04-01]: Score clamping 0-10 with rubric weights assigned server-side, not from LLM output
- [04-01]: Fallback scorecard (5.0 across all criteria) on any Gemini or parsing error
- [04-02]: XSS-safe DOM construction using createElement/textContent instead of innerHTML for score card rendering
- [04-02]: Double requestAnimationFrame for reliable CSS transition triggering on dynamically appended elements
- [04-02]: Score card as separate section below commentary, not an overlay
- [04-03]: Detached asyncio.create_task for score reveal -- must NOT block event bus callback
- [04-03]: Shared DisplayServer instance between commentary and scoring (isolation is LLM path, not display)
- [04-03]: Default track ROGUE::AGENT when operator does not specify a track
- [04-03]: Pending scorecards dict bridges timing gap between scoring completion and commentary delivery
- [05-01]: Duplicated _sanitize_team_name from ScoreStore to avoid modifying Phase 4 files
- [05-01]: Store injection_attempts as count only (not content) for security -- never persist injection payloads
- [05-01]: TeamRanking.rank is Python-assigned; total_score from ScoreStore is authoritative -- LLM provides qualitative only
- [05-02]: Gemini response_schema with Pydantic model for structured deliberation output (no manual JSON parsing)
- [05-02]: Python sorts rankings by total_score, never trusts LLM ordering
- [05-02]: Tiebreaker: total_score -> Technical Execution score -> demo_duration
- [05-02]: Observations capped at 5, transcripts at 3 per team in deliberation prompt
- [05-02]: Separate genai.Client for deliberation (isolation from commentary and scoring)
- [05-03]: Shared DisplayServer across commentary, scoring, and deliberation (isolation is LLM path, not display)
- [05-03]: Detached asyncio.create_task for deliberation display push (consistent with scoring reveal pattern)
- [05-03]: TUI deliberation via event bus only -- track assignment is CLI-only per Phase 4 pattern

### Pending Todos

None yet.

### Blockers/Concerns

- Gemini Live API 2-minute session limit needs validation with context window compression (research gap)
- NEBULA:FOG official rubric details needed for Phase 4 scoring calibration

## Session Continuity

Last session: 2026-02-16
Stopped at: Completed 05-03-PLAN.md - Deliberation pipeline integration. Phase 5 complete. Ready for Phase 6 (hardening).
Resume file: None
