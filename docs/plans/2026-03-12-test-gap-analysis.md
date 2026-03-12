# Test Gap Analysis & Priority Plan — 2026-03-12

**Context**: 1277 tests passing (including 61 new non-reward-hacking tests added today).
Event date: T-12 days. System runs 10+ hours continuously, judging ~20 teams live.

## Research Methodology

1. **Explore agent** mapped every test file against source modules, classifying each as real-behavior or tautological
2. **Brainstorm agent** found dangerous untested code paths (error recovery, race conditions, state machine edge cases)
3. **Spec panel** (3 specification reviewers) triaged IMPLEMENT NOW / DEFER / SKIP
4. **Business panel** (QA director, incident responder, event organizer) scored audience/operator/data risk

## Top 5 Must-Fix (Panel Consensus)

### 1. WebSocket JSON Format Contract Test (CRITICAL)
- **Risk**: Display shows nothing — silent total failure, no runtime warning
- **Location**: `src/commentary/display_server.py` push_* methods
- **Test**: Connect real test WebSocket, call each push method, verify JSON keys match React `audience-display/src/` type expectations
- **Effort**: 2 hours

### 2. Cross-Team Roast Bleed Guard (CRITICAL)
- **Risk**: Team A's roast appears during Team B's demo — unfair, confusing
- **Location**: `src/defense/pipeline.py` `_generate_roast` + `RoastGenerated` event
- **Root cause**: `create_task` completion is not atomic with `_on_demo_started` cancellation
- **Fix**: Tag roasts with team_name, discard if current_team doesn't match
- **Effort**: 15 minutes

### 3. Demo Timer Auto-Stop (HIGH)
- **Risk**: Capture runs forever after overtime, stale media leaks into next team's scoring
- **Location**: `src/operator/web.py` `_demo_timer_loop` line ~474 — `return`s after alert but never stops demo
- **Fix**: Call `self._demo_machine.send("stop_demo")` after overtime alert
- **Effort**: 30 minutes

### 4. Score Reveal Task Race (CRITICAL for audience)
- **Risk**: Rapid demo cycling → concurrent reveals → garbled scores on big screen
- **Location**: `src/scoring/pipeline.py` `_on_commentary_delivered` cancel-then-create pattern
- **Test**: Fire two commentary_delivered 100ms apart, verify no interleaved criterion pushes
- **Effort**: 1 hour

### 5. Operator Send Error Logging (HIGH for operator)
- **Risk**: `_send_result` swallows all exceptions with `pass` — operator blind to command failures
- **Location**: `src/operator/web.py` line ~696
- **Fix**: Log at WARNING level, surface error count on dashboard
- **Effort**: 1 hour

## Also Implement (Low Effort, High Value)

### 6. MoE Silent Degradation Warning
- **Risk**: MoE drops to single model without operator knowing
- **Fix**: Publish `ScoringDegraded` event when fewer providers respond than configured
- **Effort**: 30 minutes

### 7. OCR Health Check
- **Risk**: Tesseract not installed on venue machine = entire visual defense disabled silently
- **Fix**: Pre-event validation script confirming Tesseract works
- **Effort**: 30 minutes

## Deferred to Post-Event

| Gap | Rationale |
|-----|-----------|
| Checkpoint I/O failure | Scores in memory, crash recovery is backup path |
| Commentary timeout cleanup | Python GC handles leaked coroutines |
| Score store concurrent writes | One-file-per-team design prevents most collisions |
| Circuit breaker half-open recovery | Already tested in Phase 0 |
| Display state cache multi-team | Single-operator event |
| Deliberation persistence | End-of-event only, can re-trigger |
| Event logger stress | Append-only, already tested |
| Event bus drain timeout | Cleanup only, not live-event failure |

## Tests Added Today (61 new)

### tests/test_defense_real_behavior.py (17 tests)
- Medium→high detection flag reset via real `_on_transcript` code path
- 7 Unicode zero-width character evasion variants (U+200B, U+200D, U+00AD, U+FEFF, U+2060, U+034F, combos)
- `sanitize_transcripts` with tainted verbal injection patterns (scoring, role manipulation, delimiter escape)
- `sanitize_observations` with Gemini-style observation strings containing quoted injection text

### tests/test_scoring_real_behavior.py (15 tests)
- Real `_parse_and_validate` through ScoringPipeline (mock only `_call_gemini`, not engine)
- Score reveal argument content verification (criterion names, scores, weights, justifications)
- Malformed LLM output: partial criteria, hallucinated criteria, unparseable JSON, markdown fences
- Track validation: invalid tracks default, injection strings rejected, propagation through engine

### tests/test_commentary_tts_real_behavior.py (29 tests)
- Multi-chunk Gemini streaming assembly and sentence splitting
- TTS fallback argument content verification (`assert_called_once_with("exact text")`)
- `stream_sentences` integration: Gemini passthrough, static fallback, quota exhaustion
- MacOSSay exact subprocess arguments (voice, rate, `--` separator, text)
- Sentence splitting edge cases and emotion mapping on assembled text
