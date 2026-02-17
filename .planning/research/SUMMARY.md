# Project Research Summary

**Project:** Arbiter v1.1 -- Reliability, E2E Testing, Rehearsal Mode, MoE Hardening, Dashboard Polish
**Domain:** Event-driven async AI agent testing infrastructure, ensemble LLM scoring, operator dashboard
**Researched:** 2026-02-17
**Confidence:** HIGH

## Executive Summary

Arbiter v1.1 is a reliability and testing hardening milestone for an existing event-driven async AI judge agent. The research reveals that the current v1.0 architecture is fundamentally sound -- the EventBus pub/sub pattern, pipeline abstractions, and provider interface are proven and require zero architectural changes. The v1.1 scope adds **only test/dev tooling dependencies** (pytest-timeout, pytest-xdist, pytest-recording/vcrpy, vitest-websocket-mock) with zero new production dependencies. All new features (E2E tests, rehearsal mode, Groq scoring fallback, dashboard health indicators) are architectural patterns built on existing abstractions, not library additions.

The recommended approach is phased: (1) build test infrastructure first (pytest timeout guards, EventBus test harness, mock providers), (2) write E2E tests for the existing pipeline wiring gaps, (3) add Groq as a scoring provider using the proven OpenAI-compatible pattern from commentary fallback, (4) build rehearsal mode as input-level substitution (synthetic camera/audio data flowing through the real pipeline), and (5) surface existing backend data (ServiceHealth, ScoreStore) in the dashboard UI. This ordering respects dependencies -- tests validate existing code before new features are added, rehearsal reuses test infrastructure, and dashboard polish comes last since it has no downstream dependencies.

The key risks are async testing pitfalls (create_task event draining, pytest loop scope mismatches causing hung tests), MoE timeout cliffs (one slow provider blocking the entire ensemble for 30+ seconds), and Groq JSON format reliability (Llama 3.3 70B is less structured-output-reliable than frontier models). Mitigation: build an EventCollector pattern for deterministic async test assertions, wrap asyncio.gather in hard timeouts with partial result handling, and validate Groq scoring output empirically before declaring it operational. The existing codebase has 371+ tests using pytest-asyncio and AsyncMock -- patterns are established, just need rigorous application to the new E2E scenarios.

## Key Findings

### Recommended Stack

v1.1 adds **4 Python dev dependencies** and **1 npm devDependency** -- all test/dev tooling, zero production dependencies. The existing validated stack (Python 3.13, Gemini, Cartesia, FastAPI, React/Vite/Zustand, pytest/pytest-asyncio) requires no changes.

**Core technologies:**
- **pytest-timeout (>=2.4.0)**: Kill hanging async tests with declarative timeout config -- E2E tests spanning full pipeline can deadlock on broken event chains without timeout guards
- **pytest-xdist (>=3.5)**: Parallel test execution across cores -- 371 tests growing to 500+ with E2E additions will exceed 60s sequential runtime
- **pytest-recording + vcrpy (>=0.13.2 / >=6.0)**: Record real LLM API responses to YAML cassettes for deterministic CI replay -- prevents flaky tests from rate limits and API outages
- **vitest-websocket-mock (^0.5.0)**: Mock WebSocket server for dashboard tests -- operator dashboard is pure WebSocket client, current store tests skip connection/reconnection/error handling
- **Groq via OpenAI SDK (existing dependency)**: Llama 3.3 70B Versatile as 4th MoE scoring provider or standalone fallback -- pattern already proven in CommentaryGenerator._call_groq

**What does NOT need new libraries:**
- Rehearsal/dry-run mode: architectural pattern using existing EventBus, DemoMachine, CaptureConfig, LLMProvider abstractions
- E2E test infrastructure: AsyncMock (stdlib), existing EventBus pub/sub, Pydantic fixtures
- Dashboard health panel: ServiceHealth singleton already exists, just needs a REST endpoint

### Expected Features

v1.1 must ship 6 table-stakes features to call the system "production-ready" and 6 differentiator features for pre-event confidence. All features are reliability and testing infrastructure -- no new user-facing capabilities.

**Must have (table stakes):**
- **MoE E2E integration tests**: Full flow from ObservationVerified event through MoEScoringEngine to ScoreStore to ScoringComplete -- MoE has unit tests but zero coverage of the wiring through ScoringPipeline
- **Pipeline E2E test harness**: CapturePipeline wires 6 sub-pipelines via EventBus subscriptions with zero automated coverage -- highest risk gap in the codebase
- **Groq fallback for MoE scoring**: Commentary has 3-tier fallback (Gemini -> Groq -> static), scoring has none (all providers fail = meaningless 5.0 scorecard)
- **WebSocket reconnection indicator**: Dashboard has exponential backoff reconnect but no visual feedback -- operator cannot distinguish "reconnecting in 5s" from "server is down"
- **Health status panel**: ServiceHealth tracks per-component health but dashboard has zero visibility into TTS/Gemini/provider degradation
- **Test timeout guards**: Async tests that await broken event chains hang forever -- pytest-timeout with 30s default prevents CI deadlocks

**Should have (differentiators):**
- **Rehearsal mode (dry-run)**: Run full pipeline end-to-end with synthetic demo data and deterministic mock LLM responses -- validates wiring, timing, theatrical pacing without API keys or hardware, enables pre-event operator training
- **Event trace recording**: Record every EventBus event during live session to JSONL with timestamps -- enables post-event debugging, test fixture generation from real sessions
- **Event trace replay**: Replay recorded event trace through pipeline at original or accelerated speed -- combined with rehearsal mode creates deterministic regression tests from production data
- **MoE provider health tracking**: Track per-provider latency and error rate, auto-disable unhealthy providers mid-event via ServiceHealth -- prevents 30s timeout cliff when one provider is dead
- **Score confidence display**: ScoreAggregator already computes confidence (1.0 - stdev/10) but it's not surfaced to audience -- "MoE Confidence: 94%" for agreement adds transparency
- **Dashboard toast notifications**: lastCommandResult auto-clears after 3s but no feedback for pipeline events (injection_detected, scoring_complete) -- toast system gives awareness without polling

**Defer (v2+):**
- Playwright browser E2E tests: dashboard is thin WebSocket client, browser automation adds CI complexity for minimal coverage gain over Vitest component tests + Python WebSocket integration tests
- Real LLM calls in CI: flaky tests, costs per run, API key exposure -- use AsyncMock providers for CI, keep test_moe_demos.py as manual validation script
- Event sourcing / CQRS: EventBus is simple pub/sub, event sourcing is massive architectural change for 4-hour hackathon sessions
- Multi-instance distributed dashboard: single laptop at single event, no load balancing needed
- Automated model selection/routing: ML research project, not v1.1 scope
- Database persistence: JSON files work fine for 20-30 demos per event and enable easy debugging

### Architecture Approach

The v1.1 architecture preserves all v1.0 invariants: EventBus is the only inter-pipeline coupling, uniform wiring via pipeline.setup(event_bus), LLM client isolation, error isolation via EventBus._safe_call, typed Pydantic events, provider empty-string-on-failure contract, and module-level singletons. All new features integrate via existing interfaces -- no architectural changes.

**Major components:**
1. **PipelineTestHarness (new, test)**: Wires real pipelines (DefensePipeline, ScoringPipeline, CommentaryPipeline, DeliberationPipeline) to shared EventBus with mock I/O -- uses MockLLMProvider for deterministic responses, RehearsalGeminiSession for canned observations, existing FakeDisplayServer pattern
2. **EventCollector (new, test)**: Subscribes via EventBus.subscribe_all, captures events with timestamps, provides async wait_for(event_type, timeout) to avoid flaky sleep-based assertions -- solves create_task fire-and-forget test timing
3. **GroqProvider (new, production)**: LLMProvider impl using AsyncOpenAI with base_url="https://api.groq.com/openai/v1" and model="llama-3.3-70b-versatile" -- exact same pattern as existing ClaudeProvider/OpenAIProvider, registered in factory.py, added to MoE provider list when groq_api_key configured
4. **RehearsalRunner (new, production)**: Loads scenario JSON, drives DemoMachine state transitions, publishes synthetic events at realistic timing -- replaces capture layer (camera/audio/gemini) while downstream pipelines run identically
5. **WebOperator REST additions (new, production)**: GET /api/health endpoint returning ServiceHealth.get_status(), GET /api/scores returning ScoreStore.load_all(), event forwarding for scoring_complete and deliberation_complete via WebSocket -- dashboard consumes existing backend data with zero pipeline changes

**Critical integration points:**
- CapturePipeline.__init__ accepts optional client parameters for ScoringEngine and CommentaryGenerator (injectable for testing without monkeypatch)
- DefensePipeline.__init__ already accepts gemini_session parameter (RehearsalGeminiSession fits cleanly)
- MoEScoringEngine.score() wrapped in asyncio.wait_for with 15s hard timeout to prevent slow provider blocking entire ensemble
- Rehearsal mode is CLI flag swapping input sources, not separate code path (avoids "rehearsal passed, event failed" risk)

### Critical Pitfalls

From PITFALLS.md, the top 5 critical risks with prevention strategies:

1. **EventBus create_task tests pass by accident**: Tests publish events and immediately assert on downstream state -- passes locally because event loop schedules create_task callback before assertion, fails in CI with different scheduling. ScoringPipeline has TWO levels of create_task (observation_verified -> score() -> scoring_complete) so single await asyncio.sleep(0) drains first level only. **Prevention:** EventCollector pattern with async wait_for(event_type, timeout) instead of sleep-based assertions, drain_bus() helper for multi-level task chains.

2. **pytest-asyncio event loop scope mismatch**: E2E tests with module-scoped fixtures get "Task attached to a different loop" or hung tests because pytest-asyncio creates new loop per test function while singletons (GeminiRateLimiter, default_health, default_bus) store asyncio primitives (Semaphore, Event, Queue) bound to old loop. **Prevention:** Function-scoped async fixtures only, reset singletons in autouse fixture, never import default_* in tests, pin asyncio_default_fixture_loop_scope = "function" in pyproject.toml.

3. **MoE scoring timeout cliff -- slowest provider blocks all**: asyncio.gather waits for ALL tasks, one provider with 5 retries * 30s max wait = 150s blocking. Entire scoring call blocks while Gemini completes in 3s, breaks theatrical timing, WebSocket heartbeats missed causing false disconnection. **Prevention:** Wrap asyncio.gather in asyncio.wait_for with 15s hard timeout, cancel remaining tasks and aggregate only completed results, reduce MoE retry attempts to 2 (not 5) since ensemble tolerates individual failures.

4. **Groq scoring returns different JSON format**: Llama 3.3 70B has lower instruction-following fidelity for structured output than Gemini/Claude/GPT-4o -- returns different field names, missing fields, scores as strings not floats. ScoringEngine._parse_and_validate throws KeyError/JSONDecodeError and falls back to 5.0 default scorecard, defeating the purpose of the fallback. **Prevention:** Groq-specific JSON parsing with lenient field matching and type coercion, add "groq" to DEFAULT_CALIBRATION based on empirical testing, validate with ACTUAL scoring prompt in test_moe_demos.py before going live.

5. **Rehearsal mode that does not exercise real pipeline**: Instinct is to make rehearsal "fast and reliable" by mocking APIs, TTS, defense pipeline -- creates separate code path that tests different system than production. "Rehearsal passed, event day failed" is worst outcome. **Prevention:** Rehearsal replaces ONLY input sources (synthetic camera frames, audio chunks) via RehearsalCamera/RehearsalAudio implementing same interfaces as real capture, everything downstream runs identically including real API calls, CapturePipeline.run() wiring is identical between rehearsal and production.

## Implications for Roadmap

Based on research, suggested 4-phase structure prioritizing test infrastructure (foundation), then E2E coverage (validation), then production features (Groq fallback, rehearsal), then polish (dashboard).

### Phase 1: Test Infrastructure Foundation
**Rationale:** Foundation for everything else. E2E tests cannot be written without timeout guards (pytest-timeout), parallelism (pytest-xdist), and EventBus test helpers (EventCollector, MockLLMProvider). Without timeout, new E2E tests risk hanging CI. Without EventCollector pattern, every E2E test has flaky sleep-based assertions.

**Delivers:**
- pytest-timeout + pytest-xdist installed and configured
- pytest markers for integration/e2e/slow tests
- EventCollector test helper with async wait_for(event_type)
- MockLLMProvider returning canned JSON by prompt substring
- Singleton reset fixture for GeminiRateLimiter/default_health/default_bus
- VCR cassette configuration (optional real API recording)

**Addresses (from FEATURES.md):**
- Test timeout guards (table stakes)
- Integration test marking (table stakes)

**Avoids (from PITFALLS.md):**
- Pitfall 1: EventBus create_task flaky tests
- Pitfall 2: pytest-asyncio loop scope mismatch
- Pitfall 8: E2E tests depending on external API availability

**Confidence:** HIGH -- all tooling is stable and well-documented, patterns established in existing test suite.

### Phase 2: Pipeline E2E Coverage
**Rationale:** Validates existing v1.0 code before adding new features. CapturePipeline wiring has zero automated coverage (highest risk gap). MoE engine has unit tests but no integration tests. Writing E2E tests now catches wiring regressions and validates the test infrastructure from Phase 1 before building on it.

**Delivers:**
- PipelineTestHarness wiring real pipelines with mock I/O
- RehearsalGeminiSession for canned observations in tests
- E2E test: happy path demo_started -> score_revealed
- E2E test: MoE with 3 mock providers (Gemini, Claude, OpenAI)
- E2E test: provider failure + fallback scenarios
- E2E test: DemoMachine state transitions
- E2E test: defense pipeline injection detection -> sanitization

**Uses (from STACK.md):**
- pytest-timeout for 30s E2E test deadlines
- pytest-asyncio fixtures with function scope
- AsyncMock (stdlib) for mock providers
- EventCollector from Phase 1

**Addresses (from FEATURES.md):**
- Pipeline E2E test harness (table stakes)
- MoE E2E integration tests (table stakes)

**Avoids (from PITFALLS.md):**
- Pitfall 12: Fire-and-forget tasks in ScoringPipeline._reveal_score (discovered while testing)
- Pitfall 7: MoE calibration constants based on assumptions (run test_moe_demos.py with real providers, update DEFAULT_CALIBRATION)

**Confidence:** HIGH -- test infrastructure from Phase 1 enables deterministic E2E assertions.

### Phase 3: Groq Fallback + Rehearsal Mode
**Rationale:** Adds production reliability features using validated patterns. GroqProvider follows exact pattern from CommentaryGenerator._call_groq (proven in v1.0). Rehearsal mode reuses test infrastructure from Phase 2 (MockLLMProvider, RehearsalGeminiSession) with CLI wrapper. Both features are additive -- zero risk to existing pipeline.

**Delivers:**
- GroqProvider implementing LLMProvider base class
- Factory registration for "groq" provider
- Groq calibration in DEFAULT_CALIBRATION (empirically measured)
- MoE timeout wrapper (asyncio.wait_for with 15s deadline)
- RehearsalRunner loading scenario JSON and driving DemoMachine
- Synthetic demo fixtures (3-5 scenarios: injections, short, long, track bonus, minimal observations)
- --rehearsal CLI flag in main.py
- CapturePipeline.run() with rehearsal input substitution
- E2E test for rehearsal mode

**Uses (from STACK.md):**
- OpenAI SDK with Groq base_url (existing dependency)
- pytest-recording/vcrpy for optional Groq API cassette recording
- Existing EventBus, DemoMachine, CaptureConfig, LLMProvider abstractions

**Addresses (from FEATURES.md):**
- Groq fallback for MoE scoring (table stakes)
- Rehearsal mode dry-run (differentiator, highest value)

**Avoids (from PITFALLS.md):**
- Pitfall 3: MoE timeout cliff (hard timeout on gather)
- Pitfall 4: Groq JSON format mismatch (lenient parsing, empirical validation)
- Pitfall 5: Rehearsal mode not exercising real pipeline (input substitution only, downstream pipelines identical)
- Pitfall 9: Groq rate limits (circuit breaker, max 1 concurrent call)
- Pitfall 11: Rehearsal replays same demo (multiple diverse scenarios)

**Confidence:** HIGH for Groq (proven pattern), MEDIUM for rehearsal mode (new concept but reuses test infra).

### Phase 4: Dashboard Hardening + Polish
**Rationale:** Dashboard polish has no downstream dependencies -- can be built last. Backend endpoints expose existing data (ServiceHealth, ScoreStore) with zero pipeline changes. Frontend work is isolated to React components and Zustand store.

**Delivers:**
- GET /api/health endpoint returning ServiceHealth.get_status()
- GET /api/scores endpoint returning ScoreStore.load_all()
- WebSocket event forwarding for scoring_complete and deliberation_complete
- ScorePanel implementation (currently placeholder TODO)
- HealthIndicator component showing service health
- ConnectionDot third state (yellow "reconnecting" with backoff timer)
- Store state clearing on reconnect (fix stale data)
- Error boundary per panel
- vitest-websocket-mock tests for reconnection and error handling

**Uses (from STACK.md):**
- vitest-websocket-mock for WebSocket test mocking
- Existing FastAPI DisplayServer
- Existing Zustand operatorStore

**Addresses (from FEATURES.md):**
- WebSocket reconnection indicator (table stakes)
- Health status panel (table stakes)
- Dashboard toast notifications (differentiator, defer to v1.2)
- Operator action confirmation (differentiator, defer to v1.2)

**Avoids (from PITFALLS.md):**
- Pitfall 6: WebSocket reconnection loses state (clear store on reconnect)
- Pitfall 10: ConnectionDot has no reconnecting state (third state added)

**Confidence:** HIGH -- frontend work is isolated and testable, backend endpoints trivial.

### Phase Ordering Rationale

- **Test infra first (Phase 1):** Foundation for all subsequent work. E2E tests, rehearsal mode, and dashboard tests all depend on timeout guards and EventCollector pattern. Building this first prevents rework.
- **E2E coverage second (Phase 2):** Validates existing v1.0 code and the test infrastructure before new features are added. Catches wiring regressions early. Establishes E2E test patterns that rehearsal mode will reuse.
- **Production features third (Phase 3):** Groq and rehearsal add reliability without changing existing pipeline. Both reuse proven patterns (Groq follows CommentaryGenerator, rehearsal reuses test mocks). Safe to build after validation layer is in place.
- **Dashboard polish last (Phase 4):** Zero downstream dependencies. Frontend work can proceed in parallel with Phase 3 if needed. Low risk of affecting core pipeline.
- **Avoids pitfall cascade:** Building test infra first prevents Pitfall 1 and 2 from affecting all subsequent work. Adding MoE timeout wrapper in Phase 3 prevents Pitfall 3 from affecting production. Rehearsal design in Phase 3 prevents Pitfall 5. Dashboard fixes in Phase 4 are isolated.

### Research Flags

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Test Infrastructure):** pytest plugins are well-documented, AsyncMock patterns established in existing codebase, EventCollector follows common pub/sub testing pattern
- **Phase 2 (E2E Coverage):** Test harness design follows existing test_web_operator.py patterns, no novel integration points
- **Phase 3 (Groq Fallback):** Groq provider follows exact pattern from CommentaryGenerator._call_groq, OpenAI SDK already in use
- **Phase 4 (Dashboard Polish):** React WebSocket testing patterns well-established, FastAPI REST endpoints trivial

**Phases likely needing validation (not deep research, just empirical testing):**
- **Phase 3 (Groq Calibration):** Run test_moe_demos.py with Groq provider and real scoring prompts, measure actual bias vs. assumptions, update DEFAULT_CALIBRATION with empirical values
- **Phase 3 (Rehearsal Timing):** Validate that synthetic event timing feels realistic to operators during walkthrough rehearsal
- **Phase 4 (WebSocket Reconnection):** Test reconnection behavior with actual WiFi blips to validate stale state clearing and backoff indicator UX

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All additions are stable pytest/vitest plugins with verified compatibility. Groq via OpenAI SDK proven in existing commentary fallback. Zero new production dependencies. |
| Features | HIGH | Features derived from direct codebase analysis of gaps (CapturePipeline has zero E2E coverage, MoE wiring untested, dashboard missing health visibility). Patterns well-established in existing codebase (AsyncMock, EventBus pub/sub, ServiceHealth singleton). |
| Architecture | HIGH | All findings from direct codebase reading. New components follow existing patterns exactly (GroqProvider matches ClaudeProvider structure, RehearsalRunner uses DemoMachine API already in test fixtures). Zero architectural changes to v1.0 invariants. |
| Pitfalls | HIGH | Pitfalls derived from verified patterns in official asyncio docs and pytest-asyncio changelog. EventBus create_task timing and loop scope issues are documented gotchas. MoE timeout cliff is arithmetic from existing retry decorators. Groq JSON format is verified limitation from Groq structured outputs docs. |

**Overall confidence:** HIGH

### Gaps to Address

**Groq scoring JSON reliability (MEDIUM confidence):** Llama 3.3 70B Versatile supports json_object mode (best-effort JSON) but NOT json_schema strict mode. The existing ScoringEngine parser handles raw JSON with try/except fallback, and the MoE aggregator drops failed providers gracefully. However, Groq's actual JSON format conformance with the scoring prompt is UNKNOWN until tested empirically. **How to handle:** Run test_moe_demos.py with real Groq API calls in Phase 3 before declaring the fallback operational. Add lenient parsing (type coercion, alternate field names) if needed.

**pytest-recording compatibility with google-genai SDK (MEDIUM confidence):** VCR.py works with httpx-based SDKs (openai and anthropic both use httpx internally). The google-genai SDK uses its own gRPC/REST transport which may need filter_headers tuning. If cassettes prove unreliable, fall back to AsyncMock for Gemini-specific tests. **How to handle:** Validate in Phase 1 when configuring VCR. If Gemini cassettes are fragile, use AsyncMock for Gemini tests (acceptable -- other providers use cassettes).

**Rehearsal mode operator UX (LOW confidence):** Synthetic demo timing and event sequencing needs to "feel realistic" to operators during walkthrough rehearsal. Current plan is to use asyncio.sleep for timing gaps between events, but the right delay values are guesswork until tested. **How to handle:** Build initial rehearsal runner in Phase 3 with configurable timing, have operator test at pre-event rehearsal, adjust timing based on feedback.

**Dashboard WebSocket reconnection edge cases (LOW confidence):** Reconnection after long disconnect (>10s, multiple backoff cycles) may have edge cases around event ordering and counter staleness that aren't captured in the current design. **How to handle:** Test with actual WiFi blips in Phase 4, validate that store clearing and state push handle multi-second disconnects correctly.

## Sources

### Primary (HIGH confidence)
- Direct analysis of Arbiter codebase at /Users/scandal/ai/arbiter/ (all findings from actual code reading: src/capture/event_bus.py, src/capture/pipeline.py, src/scoring/pipeline.py, src/scoring/moe_engine.py, src/scoring/aggregator.py, src/providers/*, src/operator/web.py, src/commentary/pipeline.py, src/defense/pipeline.py, src/memory/pipeline.py, src/resilience/health.py, src/main.py, all test files, operator dashboard source)
- pytest-timeout PyPI (version 2.4.0, released May 2025)
- pytest-xdist docs (parallel test distribution, pytest 9 compatibility)
- pytest-asyncio docs (auto mode configuration, event loop scoping)
- pytest-asyncio changelog (v1.3.0 release notes, loop scope changes v0.21 to v1.0)
- Python asyncio docs: Developing with asyncio (create_task lifecycle, exception handling)
- Groq Structured Outputs docs (json_schema limited to GPT-OSS models, json_object available for Llama)
- Groq Llama 3.3 70B Versatile docs (128K context, 32K output, ~280 tok/s, json_object mode)
- vitest-websocket-mock npm (v0.5.0, auto-act() integration)
- FastAPI async test docs (httpx AsyncClient patterns)

### Secondary (MEDIUM confidence)
- pytest-recording PyPI (VCR.py pytest integration, httpx support)
- VCR.py docs (v6.0+ with httpx support, cassette filtering)
- pytest-asyncio issue #81 (hanging tests with create_task)
- pytest-asyncio concepts (event loop scope per collector)
- CPython issue #104091 (create_task recommendation for task reference storage)
- ServerlessFirst: Waiting for async tasks in E2E tests (event collector pattern)
- BBC cloudfit: Unit testing asyncio (AsyncMock patterns for pipeline testing)
- Groq Python SDK (OpenAI-compatible client with auto-retry)
- Groq docs: Rate limits (free tier 30 req/min for Llama 3.3, Dev tier 1,000 req/min)
- OneUptime: WebSockets in React (reconnection and stale state patterns)
- HookedOnUI: Real-time React WebSockets (heartbeat and status indicator patterns)

### Tertiary (LOW confidence)
- G-Research: In praise of --dry-run (dry-run mode design principles)
- arXiv 2503.13657: Why multi-agent LLM systems fail (ensemble coordination failure modes)
- CPython issue #117379 (task lifetime confusion, weak reference GC behavior)

---
*Research completed: 2026-02-17*
*Ready for roadmap: yes*
