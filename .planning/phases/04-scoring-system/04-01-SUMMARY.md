---
phase: 04-scoring-system
plan: 01
subsystem: scoring
tags: [pydantic, gemini, rubric, scoring-engine, prompt-injection-defense]

# Dependency graph
requires:
  - phase: 02-defense-pipeline
    provides: SanitizedOutput model and InjectionAttempt for scoring input
  - phase: 01-capture-layer
    provides: CaptureEvent base class for scoring events
provides:
  - RubricCriterion, TrackCriteria, CriterionScore, DemoScorecard pydantic models
  - ScoringComplete and ScoreRevealed capture events
  - Configurable GENERAL_CRITERIA (3 criteria, 40/30/30) and EXTENDED_CRITERIA (4 criteria)
  - TRACK_CRITERIA for all four NEBULA:FOG tracks
  - ScoringEngine with dedicated Gemini client for isolated scoring
affects: [04-02 score store, 04-03 scoring pipeline, 05-deliberation]

# Tech tracking
tech-stack:
  added: []
  patterns: [dedicated-gemini-client-isolation, python-computed-weighted-totals, configurable-rubric-criteria]

key-files:
  created:
    - src/scoring/__init__.py
    - src/scoring/models.py
    - src/scoring/rubric.py
    - src/scoring/engine.py
  modified: []

key-decisions:
  - "Separate genai.Client instance for scoring (SCORE-03 isolation from commentary P-LLM)"
  - "Python-computed weighted totals, never trust LLM arithmetic"
  - "Score clamping 0-10 with rubric weights assigned server-side, not from LLM output"
  - "Fallback scorecard (5.0 across all criteria) on any Gemini or parsing error"

patterns-established:
  - "Dedicated LLM client: each pipeline creates its own genai.Client for isolation"
  - "Configurable rubric: ScoringEngine accepts optional criteria parameter to override defaults"
  - "Anti-injection system prompt: explicit instructions to ignore embedded commands in observations"
  - "Markdown fence stripping: parse JSON from LLM output that may include code fences"

# Metrics
duration: 3min
completed: 2026-02-16
---

# Phase 4 Plan 1: Scoring Models and Engine Summary

**Pydantic scoring models with configurable NEBULA:FOG rubric and isolated Gemini scoring engine using Python-computed weighted totals**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-16T18:05:20Z
- **Completed:** 2026-02-16T18:08:30Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Four pydantic scoring models (RubricCriterion, TrackCriteria, CriterionScore, DemoScorecard) with field validation
- Configurable rubric with 3-criteria default (SCORE-01: 40/30/30) and 4-criteria extended variant, both summing to 1.0
- Track-specific criteria for all four NEBULA:FOG tracks (SHADOW::VECTOR, SENTINEL::MESH, ZERO::PROOF, ROGUE::AGENT)
- ScoringEngine with architecturally isolated genai.Client, anti-injection system prompt, and graceful fallback on errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Create scoring data models and configurable rubric** - `7eea0f6` (feat)
2. **Task 2: Create scoring engine with dedicated Gemini client** - `964a1f0` (feat)

## Files Created/Modified
- `src/scoring/__init__.py` - Package init
- `src/scoring/models.py` - RubricCriterion, TrackCriteria, CriterionScore, DemoScorecard, ScoringComplete, ScoreRevealed
- `src/scoring/rubric.py` - GENERAL_CRITERIA (3, 40/30/30), EXTENDED_CRITERIA (4, 30/25/20/25), TRACK_CRITERIA (4 tracks)
- `src/scoring/engine.py` - ScoringEngine with dedicated Gemini client, prompt builder, JSON parser, fallback scorecard

## Decisions Made
- Separate genai.Client instance for scoring (SCORE-03 isolation from commentary P-LLM) -- each pipeline is fully decoupled
- Python computes weighted totals from per-criterion scores; LLM only provides score + justification per criterion
- Rubric weights assigned from server-side criteria definitions, not from LLM output -- prevents weight manipulation
- Score clamping to 0.0-10.0 range protects against out-of-range LLM outputs
- Fallback scorecard returns 5.0 across all criteria with "manual review required" justification on any error
- Markdown code fence stripping handles Gemini responses wrapped in ```json fences

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Scoring models and engine ready for Plan 02 (score store/persistence)
- ScoringEngine ready for Plan 03 (scoring pipeline wiring with event bus)
- All imports verified working with existing codebase patterns

## Self-Check: PASSED

All created files verified on disk. All commit hashes verified in git log.

---
*Phase: 04-scoring-system*
*Completed: 2026-02-16*
