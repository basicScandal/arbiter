# Feature Landscape

**Domain:** Reliability/testing infrastructure, rehearsal mode, MoE scoring hardening, and operator dashboard polish for a live AI judge agent
**Researched:** 2026-02-17
**Scope:** v1.1 milestone -- NEW features only. Assumes existing v1.0 pipeline (capture, defense, commentary, scoring, deliberation, dashboard) is functional.
**Overall confidence:** HIGH (patterns well-established, codebase thoroughly analyzed)

## Table Stakes

Features that v1.1 must ship to call the MoE pipeline "production-ready" and the system testable at scale. Missing any of these means the event operator cannot trust the system under pressure.

| Feature | Why Expected | Complexity | Dependencies on Existing |
|---------|--------------|------------|--------------------------|
| **MoE E2E integration tests** | MoE engine has unit tests for aggregator + engine isolation, but zero tests verifying the full flow: `ObservationVerified` event -> `ScoringPipeline._on_observation_verified` -> `MoEScoringEngine.score()` -> `ScoreAggregator` -> `ScoreStore.save()` -> `ScoringComplete` published -> theatrical reveal via `_on_commentary_delivered`. Without this, a wiring bug between components silently breaks scoring at the event. | Med | pytest-asyncio fixtures, mock LLM providers (pattern exists in `test_scoring_aggregator.py`), EventBus test harness |
| **Pipeline E2E test harness** | `CapturePipeline` wires 6 sub-pipelines via EventBus subscriptions in its `run()` method. No test currently verifies that publishing `DemoStarted` through `DemoStopped` triggers the full downstream chain (defense sanitization -> commentary -> scoring -> display). This is the single highest-risk gap -- the glue layer has zero automated coverage. | High | EventBus test doubles, asyncio task tracking, mock Gemini/TTS/Camera/Audio, all pipeline `setup()` methods |
| **Groq fallback for MoE scoring** | Commentary already has Gemini -> Groq -> static fallback chain (`CommentaryGenerator._call_groq`). Scoring has NO provider-level fallback -- if all 3 providers (Gemini, Claude, OpenAI) fail, it returns a hardcoded 5.0 fallback scorecard via `ScoringEngine._fallback_scorecard`. Adding Groq as a 4th MoE provider (or standalone fallback) means the system degrades gracefully instead of serving meaningless scores. | Low | New `GroqProvider` implementing `LLMProvider` base class, `create_provider("groq", ...)` factory registration, `GROQ_API_KEY` already in `CaptureConfig` |
| **WebSocket reconnection indicator** | Dashboard has exponential backoff reconnection in `useOperatorSocket.ts` (1s -> 2s -> 4s -> ... -> 10s max). But `operatorStore.connected` state is only consumed by `ConnectionDot` -- there is no "Reconnecting..." banner, no retry count, no visual degradation. An operator at a live event staring at a frozen dashboard has no idea whether the system is down or reconnecting. | Low | React component reading `connected` from `useOperatorStore`, CSS transition |
| **Health status panel** | `ServiceHealth` singleton (`resilience/health.py`) tracks per-component health with exponential recovery windows. `default_health.get_status()` returns a dict of service -> healthy bool. Dashboard has zero visibility into this data -- operator cannot see which services (TTS, Gemini, providers) are degraded. | Low | New `/api/health` GET endpoint on FastAPI display server exposing `default_health.get_status()`, new `HealthPanel` React component, 5s polling or piggyback on WebSocket |
| **Test timeout guards** | Async tests that await broken event chains hang forever. With 371+ tests and more E2E tests incoming, a single hanging test blocks the entire suite. `pytest-timeout` with sensible defaults prevents CI deadlocks. | Low | `pytest-timeout` added to `[dependency-groups] dev`, timeout config in `pyproject.toml` |
| **Integration test marking** | E2E tests are inherently slower (EventBus dispatch, `asyncio.sleep` in theatrical reveals). Must be separable from fast unit tests via `pytest -m "not integration"` so developers get sub-second feedback while CI runs the full suite. | Low | `[tool.pytest.ini_options]` marker registration in `pyproject.toml`, `@pytest.mark.integration` decorators on E2E tests |

## Differentiators

Features that elevate Arbiter's testing and reliability beyond "it works on my machine." Not required for v1.1 launch, but high value.

| Feature | Value Proposition | Complexity | Dependencies on Existing |
|---------|-------------------|------------|--------------------------|
| **Rehearsal mode (dry-run)** | Run the full pipeline end-to-end using synthetic demo data with all LLM calls replaced by deterministic mock responses. Validates wiring, timing, display output, and theatrical pacing without API keys or hardware. Enables pre-event operator rehearsal ("walk the show") and CI pipeline validation. | Med | `--rehearsal` CLI flag in `main.py`, `MockLLMProvider` returning canned JSON, `MockCamera`/`MockAudio` feeding synthetic events, synthetic demo fixtures (reuse `test_moe_demos.py` DEMOS data) |
| **Event trace recording** | Record every EventBus event during a live session to a JSONL file with timestamps. Enables post-event debugging ("why did scoring take 45s for Team X?"), test fixture generation from real sessions, and regression testing by replaying traces. | Med | `EventRecorder` subscriber via `EventBus.subscribe_all`, JSONL writer with `asyncio.to_thread`, CLI `--record-events` flag |
| **Event trace replay** | Replay a recorded event trace through the pipeline at original or accelerated speed. Combined with rehearsal mode mock providers, creates fully deterministic integration tests from real production data. | Med | `EventReplayer` reading JSONL, `asyncio.sleep` for timing gaps, integration with rehearsal mode mock providers |
| **MoE provider health tracking** | Track per-provider health in MoE scoring (latency, error rate, consecutive failures) and auto-disable unhealthy providers mid-event with `ServiceHealth` integration. Currently if OpenAI is rate-limited, every subsequent MoE scoring attempt wastes timeout duration on the dead provider before `asyncio.gather` completes. | Med | Extend `MoEScoringEngine` with `ServiceHealth` check per-provider before `asyncio.gather`, latency timing around each provider call, configurable disable threshold |
| **Score confidence display** | `ScoreAggregator` already computes `confidence` (1.0 - stdev/10) in aggregation metadata. Surface this to the audience display during score reveals -- "MoE Confidence: 94%" for agreement, "Judges disagree: 67%" for divergent scores. Adds transparency and entertainment value. | Low | Add `confidence` field to `DemoScorecard` model, pass through from `_aggregate_scorecards` metadata, display in `push_total_score`, `ScorePanel` frontend update |
| **Dashboard toast notifications** | `lastCommandResult` auto-clears after 3s with `setTimeout`. No visual feedback for important pipeline events like `injection_detected`, `scoring_complete`, or `deliberation_complete`. Toast/snackbar system gives operator awareness without polling the event stream. | Low | React toast component, `dispatch` handler for specific `event_type` values in `operatorStore.ts`, auto-dismiss timer |
| **Operator action confirmation** | "Start demo" with no team name gets a silent error (`await self._send_result(ws, False, "Team name required")`). "Deliberate" with 0 demos returns nothing. Add confirmation dialogs for destructive actions (quit, reset) and validation feedback for required fields. Prevents operator mistakes at high-pressure live events. | Low | React dialog component, `CommandBar.tsx` validation logic |
| **Provider response latency overlay** | Show per-provider latency in the score panel after MoE scoring completes. "Gemini: 1.2s / Claude: 3.4s / OpenAI: 2.1s" gives operator visibility into provider performance and whether MoE is worth the extra latency. | Low | Capture `time.monotonic()` around each provider call in `MoEScoringEngine.score()`, include timing dict in `ScoringComplete` event payload, display in `ScorePanel` |

## Anti-Features

Features to explicitly NOT build for v1.1. These are tempting but wrong for this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Playwright/Cypress browser E2E tests** | The dashboard is a thin WebSocket client with Zustand state. Browser automation adds CI complexity (headless Chrome, flaky selectors, screenshot diffs) for minimal coverage gain over existing Vitest component tests + Python WebSocket integration tests. The protocol boundary IS the integration surface. | Test WebSocket message handling in Python via `fastapi.testclient.TestClient` (pattern already in `test_web_operator.py`). Test React components in Vitest (7 test files already exist). |
| **Real LLM calls in CI** | Calling Gemini/Claude/OpenAI in CI creates flaky tests (rate limits, API outages, non-deterministic responses), costs money per run, and exposes API keys in CI environments. | Use `AsyncMock` providers for all E2E tests. The existing `test_moe_demos.py` stays as a manual validation script (run with real keys before events), not in the CI suite. |
| **Event sourcing / CQRS architecture** | The EventBus is simple pub/sub with `asyncio.create_task` fire-and-forget dispatch. Retrofitting event sourcing (persistent log, replay for state reconstruction, command/query separation) is a massive architectural change for a system that runs for 4 hours at a hackathon and then shuts down. | Event trace recording (JSONL) provides debugging benefits without architectural overhead. State is ephemeral by design. |
| **Multi-instance / distributed dashboard** | Running multiple Arbiter instances or load-balanced dashboards adds WebSocket session affinity, shared state, and distributed EventBus complexity. Arbiter runs on one laptop at one event. | Keep single-instance. Multiple operator views are already handled by multi-client WebSocket broadcast (`_operator_connections` list in `WebOperator`). |
| **Automated model selection / routing** | Dynamic router picking the "best" provider per-criterion based on historical performance data. This is an ML research project, not a v1.1 feature. | Use static calibration in `ScoreAggregator` (already implemented: `DEFAULT_CALIBRATION` dict with per-model temperature + bias). Tune params between events based on `test_moe_demos.py` results. |
| **Database persistence layer** | Replacing JSON file storage (`ScoreStore`, `MemoryStore`) with SQLite/Postgres. The current file-based approach works fine for 20-30 demos per event and enables easy debugging (`cat data/scores/TeamName.json`). | Keep JSON files. They are the right tool for this scale and timeline. |

## Feature Dependencies

```
Test infrastructure (timeout, markers)
    |
    +-- Foundation for all new tests
    |
    v
EventBus test harness (EventCollector fixture)
    |
    +------+------+
    |             |
    v             v
Pipeline E2E    MoE E2E
tests           tests
    |             |
    +------+------+
           |
           v
    Rehearsal mode (reuses mock providers + adds CLI flag + synthetic fixtures)
           |
           v
    Event trace recording (EventRecorder subscriber)
           |
           v
    Event trace replay (reads JSONL, feeds EventBus)

GroqProvider (LLMProvider impl) ---------> MoE Groq scoring fallback
    |                                          |
    +-- Uses OpenAI-compatible SDK ----------> Same pattern as CommentaryGenerator._call_groq
        already proven in codebase

/api/health endpoint ----------------------> Health status panel (React)
    |
    +-- ServiceHealth.get_status() ---------> Exposes existing data, not new tracking
        already exists

WebSocket reconnection indicator ----------> Independent (reads operatorStore.connected)

MoE provider health tracking --------------> Provider latency overlay (needs timing data)
    |
    +-- ServiceHealth integration ----------> Score confidence display (needs aggregation metadata)
```

## MVP Recommendation

### Must-Have for v1.1 (Priority Order)

1. **Test infrastructure** (pytest-timeout + integration markers + EventBus test harness)
   - Rationale: Foundation for everything else. Without timeout guards, new E2E tests risk hanging CI. Without markers, slow tests slow down dev loop. Without EventBus helpers, every E2E test reimplements subscribe-and-wait boilerplate.
   - Estimated effort: Small. Mostly config + one shared fixture module.

2. **Pipeline E2E tests** (full event chain: DemoStarted -> ... -> ScoreRevealed)
   - Rationale: Highest-risk coverage gap. `CapturePipeline` wiring has zero automated tests. A broken subscription, a renamed `event_type` string, or a missing `await` silently breaks the entire flow.
   - Estimated effort: Medium. Designing representative test scenarios is the real work.

3. **MoE E2E tests** (ObservationVerified -> MoEScoringEngine -> ScoreStore -> ScoringComplete)
   - Rationale: MoE is the flagship v1.0 feature but only has unit-level coverage. The integration path through `ScoringPipeline`, provider dispatch, aggregation, and event publishing is untested.
   - Estimated effort: Medium. Can reuse patterns from pipeline E2E tests.

4. **Groq scoring fallback** (GroqProvider + factory registration)
   - Rationale: Low complexity, high reliability gain. Pattern already proven in `CommentaryGenerator._call_groq`. Closes the "all providers fail = meaningless 5.0 score" gap.
   - Estimated effort: Small. ~50 lines of code following existing pattern.

5. **Dashboard hardening** (reconnection indicator + health panel)
   - Rationale: Minimal code, maximum operator confidence. The `connected` state and `ServiceHealth` data already exist -- just need to surface them in the UI.
   - Estimated effort: Small. One new FastAPI endpoint + two React components.

6. **Rehearsal mode**
   - Rationale: Medium complexity but uniquely valuable. Pre-event operator rehearsal catches timing, display, and flow issues that unit tests cannot. Reuses mock infrastructure built for E2E tests.
   - Estimated effort: Medium. Mock components + CLI flag + synthetic fixtures.

### Defer to v1.2

- **Event trace recording/replay**: Valuable for post-event debugging but not blocking for v1.1 reliability goals. Mock-based rehearsal covers the CI use case.
- **MoE provider health tracking**: The current `asyncio.gather(return_exceptions=True)` is functional. Provider health is quality-of-life, not a reliability gap.
- **Score confidence display**: Pure polish. Data exists in aggregation metadata but surfacing requires model + frontend changes for marginal entertainment value.
- **Toast notifications + action confirmations**: UI polish improving operator UX but not affecting system reliability.
- **Provider latency overlay**: Debugging aid dependent on provider health tracking.

## Key Design Decisions

### EventBus Test Harness Pattern

The EventBus publishes via `asyncio.create_task` (fire-and-forget). Tests cannot simply publish and assert -- they must wait for async task completion. The standard pattern:

```python
class EventCollector:
    """Test helper that collects events and provides async wait-for semantics."""

    def __init__(self):
        self.events: list[CaptureEvent] = []
        self._waiters: dict[str, asyncio.Event] = {}

    async def __call__(self, event: CaptureEvent):
        self.events.append(event)
        if event.event_type in self._waiters:
            self._waiters[event.event_type].set()

    async def wait_for(self, event_type: str, timeout: float = 5.0):
        waiter = asyncio.Event()
        self._waiters[event_type] = waiter
        # Must register BEFORE publishing the triggering event
        await asyncio.wait_for(waiter.wait(), timeout=timeout)

    def get(self, event_type: str) -> list[CaptureEvent]:
        return [e for e in self.events if e.event_type == event_type]
```

Register via `event_bus.subscribe_all(collector)`. This avoids arbitrary `asyncio.sleep()` calls and makes tests deterministic. **HIGH confidence** -- well-established pattern for async pub/sub testing.

### Rehearsal Mode Architecture

Rehearsal mode is NOT a separate binary. It reuses `CapturePipeline` with injected mock components:

- `--rehearsal` CLI flag sets `config.rehearsal_mode = True`
- `CapturePipeline.__init__` checks flag and substitutes:
  - `MockCamera` -> publishes synthetic `KeyFrameDetected` events on a timer
  - `MockAudio` -> publishes synthetic `TranscriptReceived` events
  - `MockGeminiSession` -> returns canned observations from DEMOS fixtures
  - All `LLMProvider` instances -> `MockLLMProvider` returning canned scoring JSON
  - `TTSEngine` -> `MockTTSEngine` (logs speech text, skips audio playback)
- Everything else runs REAL: EventBus, DemoMachine, DefensePipeline, ScoringPipeline, CommentaryPipeline, DisplayServer, WebOperator

This validates actual wiring, timing, and display behavior with zero external dependencies.

### Groq Scoring Provider Pattern

Follow the exact pattern from `CommentaryGenerator._call_groq`:

```python
class GroqProvider(LLMProvider):
    """Groq scoring provider via OpenAI-compatible API."""

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            timeout=15.0,
        )
        self._model = model

    async def generate(self, prompt, system_prompt, *, temperature=0.3, max_tokens=1000) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception:
            logger.exception("Groq provider failed")
            return ""

    @property
    def name(self) -> str:
        return f"groq:{self._model}"
```

Register in `factory.py` as `"groq"`. Add to `CapturePipeline` MoE provider list when `config.groq_api_key` is set. Add Groq calibration to `DEFAULT_CALIBRATION` in `aggregator.py`. **HIGH confidence** -- Groq uses the OpenAI-compatible API already proven in commentary fallback.

### Health Endpoint Design

Piggyback on the existing FastAPI app in `DisplayServer`:

```python
@app.get("/api/health")
async def health():
    return {
        "services": default_health.get_status(),
        "failure_counts": {
            svc: default_health.failure_count(svc)
            for svc in default_health._healthy
        },
    }
```

Dashboard polls every 5s or receives health updates via WebSocket counter messages. **HIGH confidence** -- trivial endpoint exposing existing singleton data.

## Complexity Budget

| Category | Feature Count | Total Complexity | Notes |
|----------|--------------|------------------|-------|
| Test infrastructure | 3 (timeout, markers, harness) | Low | Config + one shared fixture module |
| E2E tests | 2 (pipeline, MoE) | Med-High | Main engineering effort: scenario design |
| Groq fallback | 1 | Low | ~50 LOC following existing pattern |
| Dashboard hardening | 2 (reconnect, health) | Low | 1 endpoint + 2 React components |
| Rehearsal mode | 1 | Med | CLI flag + mock providers + synthetic data |
| **Total v1.1 MVP** | **9 features** | **Medium overall** | Dominated by test harness design + E2E scenario authoring |

## Sources

- Arbiter codebase analysis (direct reading of `src/`, `tests/`, `operator-dashboard/`)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/en/latest/concepts.html) -- async fixture scoping, event loop management
- [FastAPI WebSocket testing](https://fastapi.tiangolo.com/tutorial/testing/) -- TestClient WebSocket support
- [FastAPI WebSocket testing patterns](https://www.compilenrun.com/docs/framework/fastapi/fastapi-websockets/fastapi-websocket-testing/) -- integration test approaches
- [pytest-timeout PyPI](https://pypi.org/project/pytest-timeout/) -- per-test timeout configuration
- [async test patterns for pytest](https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html) -- AsyncMock, event-driven test strategies
- [BBC cloudfit async testing](https://bbc.github.io/cloudfit-public-docs/asyncio/testing.html) -- AsyncMock patterns for pipeline testing
- [Groq Python SDK](https://github.com/groq/groq-python) -- OpenAI-compatible client with auto-retry
- [Groq API overview](https://console.groq.com/docs/overview) -- supported models, rate limits
- [React WebSocket reliability](https://iamrajatsingh.medium.com/enhancing-websocket-reliability-in-react-a-fallback-mechanism-for-seamless-connectivity-8b2b79659cc0) -- reconnection indicators, health monitoring
- [WebSocket dashboard patterns](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/view) -- production hardening patterns
- [pytest-xdist + async testing](https://github.com/pytest-dev/pytest-asyncio/issues/947) -- event loop compatibility
