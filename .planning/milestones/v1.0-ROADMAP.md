# Roadmap: Arbiter

## Overview

Arbiter is built in six phases following the data flow from capture to output: raw input enters, gets sanitized through a defense layer, then forks into commentary and scoring pipelines, accumulates in memory for deliberation, and finally gets hardened for live venue conditions. The dual-LLM privilege separation is foundational -- it must exist before any processing pipeline receives data, which dictates the build order. Phases 3 (Commentary) and 4 (Scoring) can execute in parallel since both consume defense layer output independently.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Capture Layer** - Camera + audio ingestion with operator-controlled demo lifecycle
- [x] **Phase 2: Defense Pipeline** - Dual-LLM privilege separation with injection detection and roasting
- [x] **Phase 3: Commentary + Output** - P-LLM persona commentary with TTS voice and text display
- [x] **Phase 4: Scoring System** - Isolated rubric-based scoring with theatrical score reveals
- [x] **Phase 5: Memory + Deliberation** - Per-demo memory storage and end-of-event comparative analysis
- [x] **Phase 6: Venue Hardening** - Failover, degraded modes, and reliability under real conditions

## Phase Details

### Phase 1: Capture Layer
**Goal**: Arbiter can see and hear live demos with clear start/stop boundaries per team
**Depends on**: Nothing (first phase)
**Requirements**: INPUT-01, INPUT-02, INPUT-03, INPUT-04, INPUT-05
**Success Criteria** (what must be TRUE):
  1. Operator can start a demo session for a named team and stop it, creating a clear capture boundary
  2. System captures camera frames at sufficient quality to read projected slides and code
  3. System captures presenter audio and produces usable text transcription
  4. Key frames (slides, code, terminal output) are extracted and available for downstream processing
  5. All capture and transcription happens in real-time during the demo, not after it ends
**Plans:** 4 plans

Plans:
- [x] 01-01-PLAN.md -- Project scaffolding, data models, config, event bus, and demo state machine
- [x] 01-02-PLAN.md -- Camera frame capture, audio capture, and key frame detection
- [x] 01-03-PLAN.md -- Gemini Live API session manager and operator CLI
- [x] 01-04-PLAN.md -- Pipeline integration wiring and end-to-end verification

### Phase 2: Defense Pipeline
**Goal**: Untrusted demo input is sanitized into structured observations before reaching any generation or scoring system
**Depends on**: Phase 1
**Requirements**: DEF-01, DEF-02, DEF-03, DEF-04, DEF-05
**Success Criteria** (what must be TRUE):
  1. Raw camera frames and audio transcription are processed by a quarantined LLM that outputs only structured observations -- the privileged LLM never sees raw input
  2. Visual injection attempts embedded in slides or terminal output are detected via OCR scanning
  3. Verbal injection attempts in presenter speech are detected from transcription
  4. Detected injection attempts trigger a generated roast response suitable for audience entertainment
  5. All injection attempts are logged with timestamp, type (visual/verbal), and content
**Plans:** 3 plans

Plans:
- [x] 02-01-PLAN.md -- Defense data models, OCR scanner, and injection detector
- [x] 02-02-PLAN.md -- Roast generator, injection logger, and observation sanitizer
- [x] 02-03-PLAN.md -- Defense pipeline orchestrator and capture integration

### Phase 3: Commentary + Output
**Goal**: Arbiter speaks and displays entertaining, persona-consistent commentary after each demo
**Depends on**: Phase 2
**Requirements**: PERS-01, PERS-02, PERS-03, OUT-01, OUT-02
**Success Criteria** (what must be TRUE):
  1. Post-demo commentary maintains a consistent Simon Cowell-meets-hacker personality that is adversarial and funny without targeting the person
  2. Commentary is spoken aloud via TTS through venue audio output
  3. Commentary and scores are simultaneously displayed as text on screen for audience readability
  4. When human judges defer Q&A to Arbiter, the system generates pointed questions based on what it observed during the demo
  5. Persona holds consistent character across multiple consecutive demos without drift
**Plans:** 3 plans

Plans:
- [x] 03-01-PLAN.md -- Install dependencies, commentary models, persona prompt, and streaming generator
- [x] 03-02-PLAN.md -- Cartesia TTS engine and FastAPI audience display server
- [x] 03-03-PLAN.md -- Q&A generator, commentary pipeline orchestrator, and main application integration

### Phase 4: Scoring System
**Goal**: Each demo receives a fair, defensible score computed from structured observations with no LLM influence on the scoring path
**Depends on**: Phase 2 (consumes defense layer output; parallel with Phase 3)
**Requirements**: SCORE-01, SCORE-02, SCORE-03, SCORE-04, SCORE-05, OUT-04
**Success Criteria** (what must be TRUE):
  1. Each demo is scored against the official NEBULA:FOG rubric (Technical Execution 40%, Innovation 30%, Demo Quality 30%) with per-criterion breakdown and brief justification
  2. Track-specific criteria are applied correctly for each track (SHADOW::VECTOR, SENTINEL::MESH, ZERO::PROOF, ROGUE::AGENT)
  3. Scoring pipeline is architecturally isolated from the LLM commentary path -- injection in the commentary path cannot affect scores
  4. A per-demo scorecard is displayed to the audience after each demo with dramatic timing and theatrical flair
**Plans:** 3 plans

Plans:
- [x] 04-01-PLAN.md -- Scoring data models, configurable rubric definitions, and dedicated scoring engine
- [x] 04-02-PLAN.md -- Score display methods on DisplayServer and theatrical score card UI in display.html
- [x] 04-03-PLAN.md -- Score persistence, scoring pipeline orchestrator, operator CLI track support, and main pipeline wiring

### Phase 5: Memory + Deliberation
**Goal**: Arbiter remembers every demo and produces comparative rankings with reasoning at the end of the event
**Depends on**: Phase 3, Phase 4
**Requirements**: MEM-01, MEM-02, MEM-03
**Success Criteria** (what must be TRUE):
  1. Structured observations (not raw input) are stored per-demo and retrievable for any previously judged team
  2. At end of event, system performs comparative deliberation across all demos with specific cross-demo references
  3. Final rankings with per-team reasoning are produced in a format human judges can review and discuss during deliberation
**Plans:** 3 plans

Plans:
- [x] 05-01-PLAN.md -- Memory data models, DemoMemory persistence store
- [x] 05-02-PLAN.md -- Deliberation engine with Gemini structured output and Python-authoritative ranking
- [x] 05-03-PLAN.md -- Deliberation pipeline orchestrator, operator commands, display integration, main wiring

### Phase 6: Venue Hardening
**Goal**: Arbiter runs reliably through a full 24-demo event under real venue conditions including network failures, TTS outages, and operator intervention
**Depends on**: Phase 3, Phase 4, Phase 5
**Requirements**: REL-01, REL-02, REL-03, OUT-03, PERS-04
**Success Criteria** (what must be TRUE):
  1. System continues operating through network interruptions without crashing or losing state
  2. When TTS fails, a secondary TTS provider activates automatically with no operator intervention
  3. System degrades gracefully -- text-only if TTS fails, cached/fallback responses if LLM is slow
  4. Operator can manually pause, resume, or override Arbiter at any point during the event
  5. TTS voice conveys emotional variety (sarcasm, surprise, genuine approval, disappointment) appropriate to commentary content
**Plans:** 3 plans

Plans:
- [x] 06-01-PLAN.md -- Resilience foundation: tenacity retry, ServiceHealth tracker, Gemini call hardening
- [x] 06-02-PLAN.md -- TTS failover chain (Cartesia -> macOS say) and expanded 12-emotion keyword map
- [x] 06-03-PLAN.md -- Operator pause/resume controls and degraded-mode text-only commentary

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6
Note: Phases 3 and 4 can execute in parallel (both depend on Phase 2, neither depends on the other).

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Capture Layer | 4/4 | ✓ Complete | 2026-02-15 |
| 2. Defense Pipeline | 3/3 | ✓ Complete | 2026-02-15 |
| 3. Commentary + Output | 3/3 | ✓ Complete | 2026-02-15 |
| 4. Scoring System | 3/3 | ✓ Complete | 2026-02-16 |
| 5. Memory + Deliberation | 3/3 | ✓ Complete | 2026-02-16 |
| 6. Venue Hardening | 3/3 | ✓ Complete | 2026-02-16 |
