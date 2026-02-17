# Domain Pitfalls — v1.1 Reliability & Polish

**Domain:** Adding E2E tests, rehearsal mode, MoE real scoring, Groq scoring fallback, and dashboard hardening to a live async event-driven AI judge agent
**Researched:** 2026-02-17
**Confidence:** HIGH (pitfalls derived from direct codebase analysis + verified patterns from official docs and community sources)

## Critical Pitfalls

Mistakes that cause rewrites, flaky CI, or live-event failures.

### Pitfall 1: EventBus create_task Tests That Pass By Accident

**What goes wrong:**
E2E tests publish events through the EventBus and immediately assert on downstream state. Tests pass locally because the event loop happens to schedule the `create_task` callback before the assertion. In CI (slower machines, different scheduling), the task has not run yet. Tests become flaky -- passing 80% of the time, failing unpredictably.

**Why it happens:**
The EventBus (line 77 of `event_bus.py`) uses `asyncio.create_task(self._safe_call(callback, event))` for non-blocking delivery. `create_task` schedules a coroutine but does NOT run it immediately. The task only executes when the event loop yields. A single `await asyncio.sleep(0)` yields once but may not be sufficient if the subscriber itself creates further tasks or awaits other coroutines. The entire subscriber chain must complete, not just the first hop.

**Why it happens in THIS codebase specifically:**
The `ScoringPipeline._on_observation_verified` handler awaits `engine.score()` (an API call or mock) then publishes `ScoringComplete` via another `create_task`. That is TWO levels of `create_task` deep. A single `await asyncio.sleep(0)` only drains the first level. The `ScoringComplete` event still has not fired when the test asserts.

**Consequences:**
- Flaky CI that erodes trust in the test suite
- Developers add arbitrary `await asyncio.sleep(0.1)` delays that slow tests and are still fragile
- False confidence: tests pass locally but the behavior they test is not actually verified

**Prevention:**
1. Create a test helper that drains all pending tasks, not just one level:
```python
async def drain_bus(loops: int = 5):
    """Yield to event loop enough times to drain multi-level create_task chains."""
    for _ in range(loops):
        await asyncio.sleep(0)
```
2. For E2E tests, use an event collector pattern: subscribe to the FINAL event in the chain and `await asyncio.wait_for(collector.received.wait(), timeout=2.0)` instead of sleep-based assertions.
3. Consider adding an `async def publish_and_wait(event)` method to EventBus for test use only, using `asyncio.Event` signaling instead of fire-and-forget.

**Detection:**
- Test passes locally but fails in CI
- Adding `await asyncio.sleep(0.05)` "fixes" a test
- Test asserts on state that depends on a subscriber of a subscriber

**Phase to address:** E2E testing phase (first phase of v1.1). This is the foundational testing infrastructure.

---

### Pitfall 2: pytest-asyncio Event Loop Scope Mismatch

**What goes wrong:**
E2E tests that share fixtures (EventBus, pipelines) across multiple test functions get `RuntimeError: Task attached to a different loop` or `Event loop is closed`. Tests hang indefinitely or produce cryptic errors about futures bound to wrong loops.

**Why it happens:**
pytest-asyncio (v0.21+) creates a NEW event loop per test function by default. Fixtures with `scope="module"` or `scope="session"` were created on one loop but tests run on another. The `GeminiRateLimiter` singleton (`rate_limiter.py` line 24) stores an `asyncio.Semaphore` bound to the loop that created it. If the loop changes between tests, the semaphore is invalid. Same problem with any `asyncio.Event`, `asyncio.Queue`, or `asyncio.Lock` stored as instance state.

**Why it happens in THIS codebase specifically:**
- `GeminiRateLimiter` is a module-level singleton with `_instance` class variable
- `default_health` in `health.py` line 78 is a module-level singleton
- `default_bus` in `event_bus.py` line 97 is a module-level singleton
- All three survive between tests but their internal asyncio primitives are bound to the old loop

**Consequences:**
- Tests hang forever waiting on a semaphore from a dead loop
- Cascading failures: one test's loop leak causes every subsequent test to fail
- Hours of debugging "works in isolation, fails in suite" problems

**Prevention:**
1. Use `@pytest.fixture` scope matching: ALL async fixtures and tests use function scope (the default). Do NOT use module/session-scoped async fixtures.
2. Reset singletons in a fixture:
```python
@pytest.fixture(autouse=True)
def reset_singletons():
    GeminiRateLimiter._instance = None
    yield
    GeminiRateLimiter._instance = None
```
3. Never import or use `default_bus` / `default_health` in tests. Always create fresh instances.
4. Pin `pytest-asyncio` mode to `auto` in `pyproject.toml` and set `asyncio_default_fixture_loop_scope = "function"`.

**Detection:**
- `RuntimeError: Task attached to a different loop`
- Tests pass individually (`pytest tests/test_foo.py::test_one`) but fail when run as a suite
- Tests hang with no output

**Phase to address:** E2E testing phase. Must be solved before writing any E2E tests.

---

### Pitfall 3: MoE Scoring Timeout Cliff — Slowest Provider Blocks All

**What goes wrong:**
MoE engine calls Gemini, Claude, and OpenAI in parallel with `asyncio.gather(*tasks, return_exceptions=True)`. One provider takes 25 seconds due to rate limiting or temporary outage. The entire scoring call blocks for 25 seconds, exceeding the comfortable time budget between demo end and score reveal. The audience sees dead air while one provider is being retried with exponential backoff (5 attempts, up to 30s max wait in `GEMINI_RETRY_BACKGROUND`).

**Why it happens:**
The current `moe_engine.py` (line 68) uses `asyncio.gather` which waits for ALL tasks. Each provider has its own retry decorator (5 attempts with exponential backoff). In the worst case, a single provider can take 5 * 30s = 150 seconds before finally failing. The gather call waits this entire time even though the other two providers completed in 3 seconds.

**Why it happens in THIS codebase specifically:**
- `GeminiProvider._call_gemini` has `GEMINI_RETRY_BACKGROUND`: 5 attempts, max 30s wait
- `ClaudeProvider._call_claude` has `CLAUDE_RETRY`: 5 attempts, max 10s wait
- `OpenAIProvider._call_openai` has `OPENAI_RETRY`: 5 attempts, max 10s wait
- Total worst-case: max(~150s, ~50s, ~50s) = 150 seconds of blocking
- The scoring pipeline holds the event bus callback for this entire duration

**Consequences:**
- Score reveal delayed by 30+ seconds after commentary finishes (breaks the theatrical flow)
- If scoring blocks the event loop for too long, WebSocket heartbeats to dashboard clients may be missed, causing false disconnection
- Audience/operator perceives system as frozen

**Prevention:**
1. Wrap the `asyncio.gather` in `asyncio.wait_for` with a hard timeout (e.g., 15 seconds):
```python
try:
    results = await asyncio.wait_for(
        asyncio.gather(*tasks, return_exceptions=True),
        timeout=15.0,
    )
except asyncio.TimeoutError:
    # Cancel remaining tasks, use whatever results completed
    ...
```
2. Better: use `asyncio.wait(tasks, timeout=15.0, return_when=ALL_COMPLETED)` which returns done and pending sets, allowing you to cancel pending and aggregate only completed results.
3. Reduce retry attempts for MoE context: when running in ensemble mode, each provider gets 2 retries (not 5) because the ensemble tolerates individual failures. The aggregator already handles partial results (line 95-107 of moe_engine.py).
4. Add per-provider timeout at the gather level, not just at the retry level.

**Detection:**
- Scoring takes >15 seconds in logs
- Score reveal happens long after commentary finishes
- Dashboard shows "scoring in progress" for extended periods

**Phase to address:** MoE E2E testing phase. Fix the timeout before running real multi-provider tests.

---

### Pitfall 4: Groq Scoring Returns Different JSON Format Than Expected

**What goes wrong:**
Groq as scoring fallback uses Llama 3.3 70B via the OpenAI-compatible API. The model is prompted to return structured JSON scoring output (criteria array with scores and justifications). Llama 3.3 has different instruction-following fidelity than Gemini/Claude/GPT-4o for structured output. It returns JSON with different field names, missing fields, extra commentary around the JSON, or scores as strings instead of floats. The `ScoringEngine._parse_and_validate` method throws `KeyError` or `json.JSONDecodeError` and falls back to the 5.0 default scorecard.

**Why it happens:**
The existing Groq fallback for commentary (`commentary/generator.py`) works because commentary output is free-form text -- any valid text is acceptable. Scoring output requires exact JSON schema compliance. Smaller/faster models (Llama 3.3 70B) are less reliable at following precise JSON schemas than frontier models. The scoring prompt was tuned for Gemini's output format and may use Gemini-specific patterns (like markdown fencing behavior) that Llama handles differently.

**Why it happens in THIS codebase specifically:**
- `ScoringEngine._parse_and_validate` expects exact field names: `criteria`, `name`, `score`, `justification`, `track_bonus`
- No JSON schema enforcement via Groq's API (Groq supports `response_format: {"type": "json_object"}` but not strict JSON schema)
- Calibration constants in `ScoreAggregator` have no entry for "groq" -- an uncalibrated Groq score would be treated with default calibration (temperature=1.0, bias=0.0), which may not be appropriate

**Consequences:**
- Groq fallback silently falls through to 5.0 default scorecard, defeating the purpose of having a fallback
- If Groq scores ARE parsed but uncalibrated, they skew the ensemble aggregate
- False sense of reliability: "we have a fallback" but the fallback never actually works for scoring

**Prevention:**
1. Add Groq-specific JSON parsing with lenient field matching and type coercion (strings to floats, alternate field names)
2. Add a `"groq"` entry to `DEFAULT_CALIBRATION` in `aggregator.py` based on empirical testing
3. Use Groq's `response_format: {"type": "json_object"}` to constrain output to valid JSON
4. Test Groq scoring output with the ACTUAL scoring prompt before going live -- run `test_moe_demos.py` with Groq as a provider
5. Consider using Groq as a single-model fallback (not ensemble member) with its own parsing path, matching the commentary fallback pattern

**Detection:**
- Groq scoring attempts always produce fallback 5.0 scorecards in logs
- `"Failed to parse response from groq"` warnings in logs
- Groq scoring latency is fast (sub-second) but results are always discarded

**Phase to address:** Groq scoring fallback phase. Must validate with real API calls before declaring the fallback operational.

---

### Pitfall 5: Rehearsal Mode That Does Not Exercise the Real Pipeline

**What goes wrong:**
Rehearsal mode is built as a separate code path that replaces camera/audio with synthetic inputs but also shortcuts other components (skips defense pipeline, uses mock scoring, bypasses TTS). The rehearsal passes perfectly but does not validate the actual pipeline. On event day, the real pipeline fails because rehearsal never tested the real component wiring.

**Why it happens:**
The instinct is to make rehearsal "fast and reliable" by mocking out slow/flaky components (API calls, TTS, camera). But each mock removes a real integration point from testing. Eventually rehearsal tests a completely different system than what runs at the venue.

**Why it happens in THIS codebase specifically:**
- `CapturePipeline.__init__` creates real camera, audio, and Gemini session objects. Rehearsal mode needs to replace these at the source (input) level, not at the pipeline level.
- The EventBus pub/sub wiring in `pipeline.run()` subscribes 8+ event handlers. If rehearsal creates a different wiring, it tests a different system.
- The scoring pipeline already conditionally uses MoE engine OR single engine (line 80-81 of `scoring/pipeline.py`). Adding rehearsal mode as a third branch further fragments the code paths.

**Consequences:**
- "Rehearsal passed, event day failed" -- the worst possible outcome
- Rehearsal becomes test theater: looks good, proves nothing
- Changes to the real pipeline are not reflected in rehearsal, creating drift

**Prevention:**
1. Rehearsal should replace ONLY the input sources (camera frames and audio chunks) with synthetic data. Everything downstream runs identically to production.
2. Inject synthetic inputs via the existing interfaces: a `RehearsalCamera` that implements the same interface as `CameraCapture` and yields pre-recorded frames, a `RehearsalAudio` that yields pre-recorded audio chunks.
3. The pipeline wiring (`CapturePipeline.run()`) should be IDENTICAL between rehearsal and production. Only the constructor swaps camera/audio implementations.
4. Real API calls should be made during rehearsal (Gemini, Claude, OpenAI, TTS) -- that is the entire point. Use a `--rehearsal-quick` flag for offline-only testing with mocks, but the default rehearsal should hit real APIs.
5. Capture rehearsal outputs (commentary text, scores, events) for comparison across runs.

**Detection:**
- Rehearsal mode has its own `run()` method separate from the main pipeline
- Rehearsal skips event bus wiring
- Rehearsal completes in <5 seconds (too fast to have hit real APIs)
- No TTS audio plays during rehearsal

**Phase to address:** Rehearsal mode phase. Design it as input substitution, not pipeline substitution.

---

## Moderate Pitfalls

### Pitfall 6: WebSocket Reconnection Loses State — Dashboard Shows Stale Data

**What goes wrong:**
Operator dashboard reconnects after a WiFi blip (common at venues). The WebSocket hook (`useOperatorSocket.ts`) reconnects and receives the initial state message, but the `events` array in the Zustand store still holds events from BEFORE the disconnect. The counters show the pre-disconnect values until the next counter push (1 second). For a brief window, the dashboard shows a mix of stale and fresh data. If a demo was started/stopped during the disconnect, the operator sees the wrong demo state.

**Why it happens:**
The current reconnection logic (lines 29-68 of `useOperatorSocket.ts`) reconnects with exponential backoff and receives a fresh state message on connect (line 99 of `web.py`: `await self._push_state(ws)`). But the state push only includes `state`, `team_name`, `track`, and `started_at`. It does NOT include current counters or event history. The store's `events` array and `counters` object retain their pre-disconnect values.

**Prevention:**
1. On reconnect, clear the `events` array and `counters` in the Zustand store BEFORE dispatching the first message:
```typescript
ws.onopen = () => {
    setConnected(true);
    backoffRef.current = 1000;
    // Clear stale state
    clearStaleState();
};
```
2. Have the server push a `counters` message immediately after the `state` message on connect, not just in the 1-second loop.
3. Add a `reconnect_count` to the store and display it in the UI during development (shows how often reconnections happen at the venue).
4. Add a visual "Reconnecting..." state to `ConnectionDot` (currently only green/red, needs yellow for reconnecting).

**Detection:**
- Dashboard shows events from a previous demo after reconnecting
- Counter numbers jump backward or forward after reconnect
- Operator is confused about current state after network blip

**Phase to address:** Dashboard hardening phase.

---

### Pitfall 7: MoE Calibration Constants Based on Assumptions, Not Data

**What goes wrong:**
The `ScoreAggregator` has hardcoded calibration constants (line 17-21 of `aggregator.py`): Gemini gets temperature 1.1 and bias -0.2, Claude gets 1.2 and bias 0.0, OpenAI gets 1.5 and bias +0.3. These values were set based on assumptions about each model's scoring tendencies. When real multi-provider scoring runs, the actual bias patterns are different. OpenAI may score lower than assumed, Claude higher. The calibration "corrects" in the wrong direction, producing LESS consistent aggregated scores than raw averaging would.

**Why it happens:**
The `test_moe_demos.py` script exists but was "never tested with real multi-provider setup" (per STATE.md blockers). The calibration constants were set without empirical data from the actual scoring prompt + rubric combination.

**Prevention:**
1. Run `test_moe_demos.py` with all three providers and collect raw scores PER CRITERION PER PROVIDER
2. Compute actual bias = (provider_mean - overall_mean) for each provider across multiple demos
3. Update `DEFAULT_CALIBRATION` with empirically measured values
4. Add a `--calibrate` flag to the test suite that outputs recommended calibration values
5. Log individual provider scores alongside aggregated scores at INFO level so calibration drift can be detected at the event

**Detection:**
- Aggregated MoE scores consistently higher or lower than any individual provider (overcorrection)
- One provider flagged as outlier on EVERY criterion (systematic miscalibration)
- Calibration constants have not changed since initial implementation

**Phase to address:** MoE E2E testing phase. Calibration update MUST happen after real multi-provider test runs.

---

### Pitfall 8: E2E Tests That Depend on External API Availability

**What goes wrong:**
E2E tests make real calls to Gemini/Claude/OpenAI APIs. One provider has an outage or rate-limits the test API key. CI fails. Developers add `@pytest.mark.skip` or mock the provider, defeating the E2E purpose. Over time, the "E2E" test suite is 80% mocked and tests nothing real.

**Why it happens:**
There is a fundamental tension between E2E test reliability (needs mocks) and E2E test value (needs real calls). The codebase already has unit tests with mocks (`test_scoring_engine.py`). Adding E2E tests that also use mocks provides no additional coverage.

**Prevention:**
1. Separate test tiers with pytest marks:
   - `@pytest.mark.unit` -- mocked, runs in CI on every push
   - `@pytest.mark.integration` -- real API calls, runs nightly or on-demand
   - `@pytest.mark.e2e` -- full pipeline with real APIs, run manually before event
2. Integration tests use `@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"))` to gracefully skip when keys are unavailable, not fail
3. Record/replay: capture real API responses once, replay in CI for deterministic testing (VCR pattern)
4. The existing `test_moe_demos.py` is actually an integration test disguised as a unit test -- it should be marked and separated

**Detection:**
- CI fails due to API rate limits or outages
- Developers skip tests to unblock CI
- "E2E" tests complete in <1 second (means nothing real was called)

**Phase to address:** E2E testing phase. Tier separation is a prerequisite for sustainable testing.

---

### Pitfall 9: Groq Rate Limits Are Lower Than Expected for Scoring

**What goes wrong:**
Groq's free tier has strict rate limits: 30 requests/minute for Llama 3.3 70B, with 15,000 tokens/minute input limit. When Groq is used as scoring fallback during a burst (Gemini fails, all 3-5 pending scoring requests cascade to Groq), the rate limit is hit immediately. All Groq scoring calls fail with 429 errors. The "fallback" has the same failure mode as the primary.

**Why it happens:**
Commentary fallback to Groq works because it is a single call per demo. Scoring fallback could face burst traffic if Gemini fails during a sequence of rapid demo stops. The Groq rate limiter is not coordinated with the existing `GeminiRateLimiter` semaphore pattern.

**Prevention:**
1. Add a `GroqRateLimiter` or extend the existing rate limiter pattern to cover Groq calls
2. Groq scoring fallback should use a queue with max 1 concurrent call, not fire-and-forget
3. If using Groq for scoring, use the Dev tier ($0 with higher limits: 1,000 req/min) or a paid plan
4. Implement circuit breaker: if Groq fails twice in a row, mark it unhealthy via `ServiceHealth` and stop trying for 60 seconds

**Detection:**
- `429 Too Many Requests` in Groq scoring logs
- Multiple teams scored with fallback 5.0 in rapid succession
- Groq scoring works for demo #1 but fails for demos #2-3 in quick succession

**Phase to address:** Groq scoring fallback phase.

---

## Minor Pitfalls

### Pitfall 10: Dashboard ConnectionDot Has No "Reconnecting" State

**What goes wrong:**
The `ConnectionDot` component (lines 3-16 of `ConnectionDot.tsx`) shows green (connected) or red (disconnected). During reconnection with exponential backoff (up to 10 seconds), the dot shows red the entire time. The operator cannot distinguish between "reconnecting after a blip" (wait 5 seconds) and "server is down" (restart the system). This causes unnecessary panic at the venue.

**Prevention:**
Add a third state: yellow/amber pulsing dot for "reconnecting" with the current backoff timer displayed as tooltip. Track reconnection state in the Zustand store.

**Phase to address:** Dashboard hardening phase.

---

### Pitfall 11: Rehearsal Mode Replays Same Demo Every Time

**What goes wrong:**
Rehearsal mode uses a single hardcoded synthetic demo. Operators rehearse 3 times, get identical output each time, and conclude the system works. On event day, a demo with unusual characteristics (very short, no transcript, many injection attempts) triggers an untested code path.

**Prevention:**
Include 3-5 diverse synthetic demos that exercise different code paths: one with injections, one very short, one very long, one with track bonus, one with minimal observations. Cycle through them on each rehearsal run.

**Phase to address:** Rehearsal mode phase.

---

### Pitfall 12: Fire-and-Forget Tasks in ScoringPipeline._on_commentary_delivered

**What goes wrong:**
Line 119 of `scoring/pipeline.py`: `asyncio.create_task(self._reveal_score(scorecard))` creates a fire-and-forget task for the theatrical reveal. If this task raises an exception, it is logged by the task's exception handler but NOT by the event bus's `_safe_call` wrapper (because `_on_commentary_delivered` already returned). The task reference is not stored, making it eligible for garbage collection before completion (Python GC collects unreferenced tasks).

**Prevention:**
Store the task reference: `self._reveal_task = asyncio.create_task(...)`. Add the task to a set and remove on completion:
```python
self._background_tasks: set[asyncio.Task] = set()
task = asyncio.create_task(self._reveal_score(scorecard))
self._background_tasks.add(task)
task.add_done_callback(self._background_tasks.discard)
```

**Phase to address:** E2E testing phase (discovered while writing tests for the reveal flow).

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| E2E testing infrastructure | Pitfall 1 (create_task draining), Pitfall 2 (loop scope), Pitfall 8 (API dependency) | Build drain helper and singleton reset fixture FIRST. Tier tests by mark. |
| Rehearsal mode | Pitfall 5 (fake pipeline), Pitfall 11 (single demo) | Input substitution only. Multiple synthetic scenarios. |
| MoE real scoring | Pitfall 3 (timeout cliff), Pitfall 7 (calibration), Pitfall 12 (fire-and-forget) | Hard timeout on gather. Run calibration test. Store task refs. |
| Groq scoring fallback | Pitfall 4 (JSON format), Pitfall 9 (rate limits) | Test with real prompt. Add rate limiter. Circuit breaker. |
| Dashboard hardening | Pitfall 6 (stale state), Pitfall 10 (reconnecting indicator) | Clear store on reconnect. Add third connection state. |

## Sources

- [Python asyncio docs: Developing with asyncio](https://docs.python.org/3/library/asyncio-dev.html) -- Official guidance on create_task lifecycle and exception handling
- [Python asyncio docs: create_task pitfalls](https://runebook.dev/en/docs/python/library/asyncio-eventloop/asyncio.loop.create_task) -- Fire-and-forget task GC risk
- [CPython issue #104091: create_task recommendation](https://github.com/python/cpython/issues/104091) -- Discussion of task reference storage best practice
- [CPython issue #117379: Task lifetime confusion](https://github.com/python/cpython/issues/117379) -- Weak reference GC behavior
- [pytest-asyncio issue #81: Event loop hanging](https://github.com/pytest-dev/pytest-asyncio/issues/81) -- Hanging tests with create_task
- [pytest-asyncio concepts: Event loop scope](https://pytest-asyncio.readthedocs.io/en/latest/concepts.html) -- Loop scope per collector
- [pytest-asyncio discussion #1171: Loop changes v0.21 to v1.0](https://github.com/pytest-dev/pytest-asyncio/discussions/1171) -- Breaking changes in loop management
- [ServerlessFirst: Waiting for async tasks in E2E tests](https://serverlessfirst.com/emails/how-to-wait-for-an-async-task-to-complete-inside-an-e2e-test/) -- Event collector pattern
- [BBC cloudfit: Unit testing asyncio](https://bbc.github.io/cloudfit-public-docs/asyncio/testing.html) -- Async test patterns
- [Groq docs: Rate limits](https://console.groq.com/docs/rate-limits) -- Free/Dev tier limits (30 req/min for Llama 3.3)
- [G-Research: In praise of --dry-run](https://www.gresearch.com/news/in-praise-of-dry-run/) -- Dry-run mode design principles
- [arXiv 2503.13657: Why multi-agent LLM systems fail](https://arxiv.org/pdf/2503.13657) -- Ensemble coordination failure modes
- [OneUptime: WebSockets in React](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/view) -- Reconnection and stale state patterns
- [HookedOnUI: Real-time React WebSockets](https://hookedonui.com/real%E2%80%91time-react-implementing-websockets-without-the-headaches/) -- Heartbeat and status indicator patterns

---
*Pitfalls research for: Arbiter v1.1 Reliability & Polish -- NEBULA:FOG 2026*
*Researched: 2026-02-17*
