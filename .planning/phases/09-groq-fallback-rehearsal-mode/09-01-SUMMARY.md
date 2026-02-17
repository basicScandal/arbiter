---
phase: 09-groq-fallback-rehearsal-mode
plan: 01
subsystem: scoring
tags: [groq, llama, moe, asyncio, timeout, openai-compatible]

# Dependency graph
requires:
  - phase: 05-scoring-engine
    provides: "MoEScoringEngine, ScoreAggregator, ScoringPipeline"
  - phase: 04-multi-provider
    provides: "LLMProvider ABC, provider factory, OpenAIProvider pattern"
provides:
  - "GroqProvider LLMProvider implementation with JSON mode"
  - "Timeout-bounded MoE scoring via asyncio.wait (15s hard cap)"
  - "Groq neutral calibration defaults in ScoreAggregator"
  - "Groq wired into MoE provider list in CapturePipeline"
affects: [09-02-PLAN, 10-dashboard-hardening]

# Tech tracking
tech-stack:
  added: [groq-api]
  patterns: [openai-compatible-provider, asyncio-wait-timeout, partial-result-aggregation]

key-files:
  created: [src/providers/groq_provider.py]
  modified: [src/providers/factory.py, src/providers/__init__.py, src/scoring/aggregator.py, src/scoring/moe_engine.py, src/capture/pipeline.py]

key-decisions:
  - "Groq uses OpenAI-compatible SDK with base_url override, not a separate Groq SDK"
  - "JSON mode enforced via response_format for reliable scoring output"
  - "Neutral calibration (temperature=1.0, bias=0.0) pending empirical tuning"
  - "asyncio.wait replaces asyncio.gather for partial-result support on timeout"

patterns-established:
  - "OpenAI-compatible provider: reuse AsyncOpenAI with base_url for third-party APIs"
  - "Timeout-bounded concurrency: asyncio.wait + cancel + await cleanup pattern"

# Metrics
duration: 4min
completed: 2026-02-17
---

# Phase 9 Plan 1: Groq Fallback & MoE Timeout Summary

**GroqProvider via OpenAI-compatible API with JSON mode, plus 15-second asyncio.wait timeout replacing asyncio.gather in MoE engine for partial-result resilience**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-17T18:01:12Z
- **Completed:** 2026-02-17T18:05:55Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- GroqProvider class implemented following OpenAIProvider pattern with JSON mode enforcement
- Provider factory, exports, and calibration updated to include Groq
- MoE engine hardened with asyncio.wait timeout -- slow providers cancelled, partial results preserved
- CapturePipeline includes Groq in MoE ensemble when GROQ_API_KEY is configured
- All 388 existing tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement GroqProvider and wire into provider system** - `ab3535d` (feat)
2. **Task 2: Replace asyncio.gather with timeout-bounded asyncio.wait in MoE engine** - `dce647e` (feat)

## Files Created/Modified
- `src/providers/groq_provider.py` - GroqProvider LLMProvider using AsyncOpenAI with Groq base URL
- `src/providers/factory.py` - Added groq case to create_provider factory
- `src/providers/__init__.py` - Added GroqProvider to package exports
- `src/scoring/aggregator.py` - Added neutral groq calibration defaults
- `src/scoring/moe_engine.py` - Replaced asyncio.gather with asyncio.wait + 15s timeout
- `src/capture/pipeline.py` - Wired Groq into MoE provider list

## Decisions Made
- Used OpenAI-compatible SDK (AsyncOpenAI with base_url) rather than a separate Groq SDK -- reduces dependencies, follows established OpenAIProvider pattern
- Enforced JSON output mode via response_format={"type": "json_object"} for reliable scoring rubric responses
- Set neutral calibration defaults (temperature=1.0, bias=0.0) -- awaits empirical tuning in production
- asyncio.wait with ALL_COMPLETED + timeout replaces asyncio.gather -- enables partial results when providers hang

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Groq integration activates when GROQ_API_KEY environment variable is set.

## Next Phase Readiness
- GroqProvider ready for use in MoE scoring ensemble
- Timeout-bounded concurrency protects against slow providers
- Ready for Phase 9 Plan 2 (rehearsal mode)

## Self-Check: PASSED

- FOUND: src/providers/groq_provider.py
- FOUND: 09-01-SUMMARY.md
- FOUND: ab3535d (Task 1 commit)
- FOUND: dce647e (Task 2 commit)

---
*Phase: 09-groq-fallback-rehearsal-mode*
*Completed: 2026-02-17*
