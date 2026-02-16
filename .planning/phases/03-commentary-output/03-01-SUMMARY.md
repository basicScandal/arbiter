---
phase: 03-commentary-output
plan: 01
subsystem: commentary
tags: [gemini, streaming, pydantic, persona-prompt, cartesia, fastapi, tts]

# Dependency graph
requires:
  - phase: 02-defense-pipeline
    provides: "SanitizedOutput model consumed by CommentaryGenerator"
  - phase: 01-capture-layer
    provides: "CaptureEvent base class for commentary event types"
provides:
  - "Commentary, QAQuestion, DisplayUpdate pydantic models"
  - "QARequested, CommentaryDelivered, TTSSpeaking, TTSFinished event types"
  - "PERSONA_PROMPT with Simon Cowell-meets-hacker persona and calibration examples"
  - "QA_PROMPT for targeted Q&A question generation"
  - "CommentaryGenerator with async Gemini streaming generation"
affects: [03-02, 03-03, 04-scoring-engine]

# Tech tracking
tech-stack:
  added: [cartesia~=3.0, fastapi~=0.129, uvicorn, jinja2]
  patterns: [fresh-generate-per-demo, sentence-streaming, emotion-mapping]

key-files:
  created:
    - src/commentary/__init__.py
    - src/commentary/models.py
    - src/commentary/prompts.py
    - src/commentary/generator.py
  modified:
    - pyproject.toml

key-decisions:
  - "Gemini 2.5 Flash for commentary generation (fast, already in stack)"
  - "Fresh generate_content_stream per demo with full persona prompt to prevent drift"
  - "Regex sentence splitting on .!? for TTS chunking"
  - "Keyword-based emotion mapping (sarcastic/content/disappointed) for Cartesia TTS"

patterns-established:
  - "Per-demo persona prompt: Full system_instruction on every call, no chat history accumulation"
  - "Sentence-level emotion mapping: Classify each sentence for Cartesia emotion control"
  - "Graceful generation fallback: Return fallback text on Gemini error instead of crashing"

# Metrics
duration: 2min
completed: 2026-02-15
---

# Phase 3 Plan 1: Commentary Foundation Summary

**Pydantic commentary models, Simon Cowell persona prompt with 5 calibration examples, and async streaming Gemini commentary generator**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-16T07:36:47Z
- **Completed:** 2026-02-16T07:39:08Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Installed 4 new dependencies (cartesia, fastapi, uvicorn, jinja2) for Phase 3
- Created 7 Pydantic model classes: Commentary, QAQuestion, DisplayUpdate, QARequested, CommentaryDelivered, TTSSpeaking, TTSFinished
- Built PERSONA_PROMPT (2560 chars) with identity anchoring, tone rules, 5 calibration examples, injection handling, and output format constraints
- Implemented CommentaryGenerator with async Gemini streaming, sentence splitting, and emotion mapping

## Task Commits

Each task was committed atomically:

1. **Task 1: Install dependencies and create commentary models** - `2f98322` (feat)
2. **Task 2: Create persona prompt and streaming commentary generator** - `3780bb5` (feat)

## Files Created/Modified
- `pyproject.toml` - Added cartesia, fastapi, uvicorn, jinja2 dependencies
- `src/commentary/__init__.py` - Package marker for commentary module
- `src/commentary/models.py` - Commentary, QAQuestion, DisplayUpdate, and 4 event type models
- `src/commentary/prompts.py` - PERSONA_PROMPT and QA_PROMPT constants
- `src/commentary/generator.py` - CommentaryGenerator with async streaming generation

## Decisions Made
- Used Gemini 2.5 Flash (not 2.0 Flash) for commentary -- higher quality justifiable since commentary is the primary output
- Fresh generate_content_stream per demo with full persona prompt prevents persona drift across 24 demos
- Simple regex sentence splitting (`(?<=[.!?])\s+`) is adequate for conversational LLM output
- Keyword-based emotion mapping (sarcastic default, content for praise, disappointed for critique) provides baseline emotion control for Cartesia TTS

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Commentary models ready for TTS engine (Plan 02) and display server (Plan 03)
- CommentaryGenerator ready for pipeline wiring in Plan 03
- PERSONA_PROMPT and QA_PROMPT ready for all commentary generation
- Event types (TTSSpeaking, TTSFinished, etc.) ready for event bus integration

## Self-Check: PASSED

- [x] src/commentary/__init__.py - FOUND
- [x] src/commentary/models.py - FOUND
- [x] src/commentary/prompts.py - FOUND
- [x] src/commentary/generator.py - FOUND
- [x] Commit 2f98322 - FOUND
- [x] Commit 3780bb5 - FOUND

---
*Phase: 03-commentary-output*
*Completed: 2026-02-15*
