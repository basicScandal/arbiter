# Arbiter Real-World Testing Strategy

**Date**: 2026-02-27
**Status**: Approved
**Timeline**: 4 weeks before NEBULA:FOG 2026

## Problem Statement

Arbiter has 704 unit tests across 42 Python files and 9 React component tests.
However, 912 mock/fake/patch references across 27 files means the vast majority
of tests run against mocked dependencies. The VCR cassettes directory is empty
despite infrastructure being configured. No test exercises real LLM API
responses, real TTS audio, real WebSocket connections under load, or real
hardware.

The system works in theory. We need to prove it works in practice.

## Four Failure Scenarios (All Critical)

1. **FM1: LLM API failures mid-demo** -- Gemini/Claude/OpenAI goes down or
   times out during live scoring, system doesn't recover gracefully
2. **FM2: Prompt injection succeeds** -- audience or demo team tricks the judge
   through OCR text, audio, or visual content
3. **FM3: System freezes under load** -- WebSocket drops, TTS queues back up,
   scoring delays, experience degrades during 3-5 minute demo window
4. **FM4: Scoring inconsistency** -- multi-model voting produces wildly
   different results, deliberation makes unfair comparisons

## Constraints

- **Timeline**: 4+ weeks before event
- **Hardware**: No venue access until event day -- testing on dev machines only
- **Infrastructure appetite**: Full send -- willing to build dedicated test
  harness, chaos engineering, whatever it takes

## Five Known Bugs (Expert Consensus)

These were identified independently by multiple expert perspectives and will
cause problems at the live event if unfixed.

### Bug 1: Circuit Breaker Has No Reset (Critical)

`GeminiCircuitBreaker` has `trip()` but no `reset()` and no half-open state.
A transient 30-second Gemini outage early in the event permanently disables
Gemini scoring for the remaining 4+ hours. A transient failure becomes permanent
degradation.

**Fix**: Add half-open state with 60s cooldown. After cooldown, allow one probe
request. If it succeeds, reset to closed. If it fails, stay open for 120s.
~15 lines of code.

**File**: `src/resilience/circuit_breaker.py`

### Bug 2: No End-to-End Timeout Budget (Critical)

Individual component timeouts exist (MOE_TIMEOUT=15s, COMMENTARY_TIMEOUT=30s,
retry backoff up to 30s x 5 attempts) but no holistic timeout says "the entire
scoring + commentary + reveal sequence MUST complete within 60 seconds." If
Gemini retries 5x at 30s backoff, audience stares at blank screen for 2+ minutes
before fallback begins.

**Fix**: Add an outer timeout wrapping the full pipeline from `demo_stopped`
to `scoring_complete`, with aggressive cancellation and fallback after 45s.

### Bug 3: Injection False Positives on Security Demos (High)

Regex patterns include "ignore previous instructions" and "give perfect score"
-- phrases that legitimately appear in security hackathon demo explanations.
Teams demonstrating injection defenses could have observations stripped, leading
to unfairly lower scores. False positive rate against real hackathon content is
completely untested.

**Fix**: Build injection test corpus with false-positive regression suite.
Adjust confidence thresholds so single keyword mentions at "low" confidence
don't trigger removal.

**File**: `src/defense/injection_detector.py`

### Bug 4: TTS Queue Not Cancelled on Demo Transition (High)

`TTSEngine` has `_speak_lock` that serializes speech. If commentary generates
10 sentences at 3s each, there's a 30-second queue. If the operator starts a
new demo during playback, the audience hears stale commentary for the wrong
team. No `cancel_pending()` method exists.

**Fix**: Add cancellation mechanism triggered by `demo_started` event that
clears the TTS queue within 1 second.

**File**: `src/commentary/tts_engine.py`

### Bug 5: MoE Calibration Constants Are Guesses (High)

`ScoreAggregator` calibration parameters (temperature, bias per provider) have
a comment on line 22 that literally says "Neutral defaults -- needs empirical
calibration." No calibration data from real provider responses exists.

**Fix**: Run calibration script with real API keys, collect empirical data,
replace hardcoded defaults.

**File**: `src/scoring/aggregator.py`

## Implementation Phases

### Phase 0: Immediate Wins (Day 1-2)

Zero infrastructure required. Highest ROI per hour invested.

| # | Action | Effort | Addresses |
|---|--------|--------|-----------|
| 0.1 | Record VCR cassettes -- run scoring against live APIs, capture real responses (success + 429 errors) | 1h | All |
| 0.2 | Injection test corpus -- `tests/injection_corpus.py` with 50+ attack payloads AND 20+ false-positive security-discussion texts | 3-4h | FM2 |
| 0.3 | Fix circuit breaker -- add half-open state with 60s cooldown probe | 1h | FM1 |
| 0.4 | `make smoke` command -- starts rehearsal, connects WS, runs 1 demo, asserts valid score in <60s | 2-4h | All |

### Phase 1: Chaos Layer (Week 1)

Build fault injection into existing test infrastructure.

- **Cascading failure integration test**: Real circuit breaker + retry +
  fallback chain. Mock only HTTP calls via VCR cassettes. Full path:
  `HTTP 429 -> tenacity retry -> DailyQuotaExhausted -> circuit breaker trip ->
  Claude fallback -> valid scorecard`
- **End-to-end timeout budget test**: Inject real 20-second delay on Gemini
  scoring. Measure wall-clock time to `scoring_complete`. Assert < 45 seconds.
- **TTS queue drain test**: Start 10-sentence TTS, after 2 sentences publish
  `DemoStarted`. Assert remaining 8 cancelled within 1 second.
- **Event bus backpressure monitor**: WARNING at 20 pending tasks, ERROR at 50.
  Wire into `Metrics` singleton.

### Phase 2: Red Team + Scoring Gauntlet (Week 2)

- Full injection corpus testing against all 11 regex patterns
- Scoring consistency: same `SanitizedOutput` x5 per provider, measure stdev
  (target: < 1.0 per criterion)
- 20-demo drift test: identical demos scored sequentially, #1 vs #20 delta
  (target: < 0.5 points)
- Calibration data collection to replace "Neutral defaults" comment
- Multi-demo state accumulation: 5 consecutive demos verifying memory store,
  score store, deliberation, subscriber count, singleton state

### Phase 3: Dress Rehearsal (Week 3)

Physical setup: camera -> monitor with slides, mic -> speakers with narration.

5 full demo cycles with real API keys, real TTS, real WebSocket dashboards.

Timing checklist (measured with stopwatch):
- Demo stop -> commentary on display: < 10s
- Demo stop -> TTS audio begins: < 15s
- Commentary delivered -> score reveal: < 5s
- Full cycle (demo stop -> scores visible): < 60s

Sabotage scenarios:
- Kill WiFi 15s mid-scoring (demo #3)
- Hold up injection text (demo #4)
- Two operators connect simultaneously, issue conflicting commands

### Phase 4: Chaos Marathon (Week 3-4)

Docker Compose sustained load test:
- 20 consecutive synthetic demos, randomized timing
- toxiproxy on all external APIs (latency, packet loss, connection resets)
- 10 operator + 50 audience WebSocket connections
- Assertions: memory < 500MB, asyncio tasks < 50, WS latency < 100ms
- Random network kill switch (15-30s) for correlated failure testing

## Priority Matrix

| Priority | Item | Failure Mode | Impact | Effort |
|----------|------|-------------|--------|--------|
| P0 | Record VCR cassettes | All | Critical | 1h |
| P0 | `make smoke` command | All | Critical | 2-4h |
| P0 | Fix circuit breaker | FM1 | Critical | 1h |
| P1 | Injection test corpus | FM2 | High | 3-4h |
| P1 | Cascading failure test | FM1 | High | 4-6h |
| P1 | TTS queue drain test | FM3 | High | 3-5h |
| P1 | Multi-demo accumulation test | FM3, FM4 | High | 4-6h |
| P2 | Dress rehearsal | All | High | 6-8h |
| P2 | Scoring consistency suite | FM4 | High | 4-6h |
| P2 | WebSocket reconnection test | FM3 | Medium | 4-6h |
| P3 | Chaos marathon | FM1, FM3 | Medium | 8-12h |
| P3 | Exploratory testing sessions | FM2, FM3 | Medium | 3x45m |

## Success Criteria

The system is ready for the live event when:

1. `make smoke` passes consistently
2. VCR cassettes capture real API response shapes and error formats
3. Circuit breaker recovers from transient failures within 120 seconds
4. Injection detection rate > 95%, false positive rate < 5%
5. Scoring variance < 1.0 stdev per criterion across 5 identical runs
6. Full dress rehearsal completes 5 demos with all timing targets met
7. 20-demo chaos marathon completes without freeze or memory leak

## Analysis Sources

This strategy was synthesized from four parallel analyses:

1. **Brainstorming session**: Interactive constraint discovery and layer design
2. **Research agent**: Best practices for testing real-time AI/ML systems,
   WebSocket reliability, chaos engineering, multi-model consensus
3. **Business panel** (Taleb, Nygard, Meadows, Drucker): Risk analysis,
   antifragility, systems thinking, ROI prioritization
4. **Spec panel** (Crispin, Nygard, Wiegers, Adzic): Testing quadrant gaps,
   stability patterns, requirements engineering, specification by example
