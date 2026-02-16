---
phase: 05-memory-deliberation
plan: 02
subsystem: deliberation
tags: [gemini, structured-output, ranking, comparative-analysis, pydantic]

# Dependency graph
requires:
  - phase: 05-memory-deliberation-01
    provides: DemoMemory, DeliberationResult, TeamRanking models
  - phase: 04-scoring-system
    provides: DemoScorecard, ScoreStore for authoritative scores
provides:
  - DeliberationEngine with Gemini structured output for comparative analysis
  - Python-authoritative ranking with tiebreaker logic
  - DELIBERATION_SYSTEM_PROMPT with anti-injection and Arbiter persona
affects: [05-memory-deliberation-03, deliberation-pipeline, operator-cli]

# Tech tracking
tech-stack:
  added: []
  patterns: [gemini-response-schema, python-authoritative-ranking, sanitized-name-matching]

key-files:
  created:
    - src/memory/deliberation_engine.py
  modified: []

key-decisions:
  - "Gemini response_schema with Pydantic model for structured output instead of manual JSON parsing"
  - "Python sorts rankings by total_score from ScoreStore, never trusts LLM ordering"
  - "Tiebreaker: total_score -> Technical Execution score -> demo_duration"
  - "Observations capped at 5, transcripts at 3 per team in deliberation prompt"
  - "Sanitized name matching for cross-store team lookup (same regex as ScoreStore)"
  - "Separate genai.Client instance for deliberation (isolation from commentary and scoring)"

patterns-established:
  - "Gemini structured output: response_schema=PydanticModel with response_mime_type=application/json"
  - "Cross-store joining via sanitized team name regex matching"

# Metrics
duration: 2min
completed: 2026-02-16
---

# Phase 5 Plan 2: Deliberation Engine Summary

**Comparative deliberation engine using Gemini structured output with Python-authoritative ranking and tiebreaker logic**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-16T19:03:32Z
- **Completed:** 2026-02-16T19:05:24Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- DeliberationEngine with dedicated genai.Client (isolation pattern matching ScoringEngine)
- Gemini response_schema=DeliberationResult eliminates all manual JSON parsing
- Python-authoritative ranking sorts by total_score, then Technical Execution, then demo_duration
- Deliberation prompt builder caps per-team data (5 obs, 3 transcripts) to prevent context overflow
- Anti-injection instruction in system prompt to resist manipulation from observation content
- Sanitized name matching joins memories to scorecards reliably across stores

## Task Commits

Each task was committed atomically:

1. **Task 1: Deliberation engine with Gemini structured output and Python-authoritative ranking** - `1a8e832` (feat)

## Files Created/Modified
- `src/memory/deliberation_engine.py` - DeliberationEngine class with Gemini structured output, DELIBERATION_SYSTEM_PROMPT constant, prompt builder, and Python-authoritative ranking with tiebreakers

## Decisions Made
- Used Gemini response_schema (structured output) instead of manual JSON parsing -- cleaner and more reliable than Phase 4's fence-stripping approach for new code
- Separate genai.Client instance for deliberation, maintaining architectural isolation from both commentary and scoring LLM paths
- Tiebreaker includes demo_duration from memories (longer demo = more ambitious) as third sort key
- Sanitized name matching uses same regex as ScoreStore._sanitize_team_name() for reliable cross-store joins
- Errors propagate to operator (deliberation is manual trigger, not automatic pipeline) -- no fallback/silent failure

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added memories parameter to _apply_authoritative_ranking for demo_duration tiebreaker**
- **Found during:** Task 1
- **Issue:** Plan specified demo_duration as third tiebreaker but _apply_authoritative_ranking signature only took result and scorecards. DemoScorecard does not contain demo_duration -- that data lives in DemoMemory.
- **Fix:** Extended _apply_authoritative_ranking to accept memories list, built duration_by_team lookup for complete tiebreaker implementation.
- **Files modified:** src/memory/deliberation_engine.py
- **Verification:** Method signature updated, sort_key uses all three criteria
- **Committed in:** 1a8e832

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Auto-fix necessary to implement the tiebreaker spec correctly. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DeliberationEngine ready for integration in Plan 03 (DeliberationPipeline orchestrator)
- Requires MemoryStore (Plan 01) and ScoreStore (Phase 04) to provide data at deliberation time
- Operator "deliberate" command will trigger the pipeline which calls this engine

---
*Phase: 05-memory-deliberation*
*Completed: 2026-02-16*
