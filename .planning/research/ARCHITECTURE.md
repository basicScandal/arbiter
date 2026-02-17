# Architecture Patterns: v1.1 Reliability & Testing

**Domain:** Reliability infrastructure, E2E testing, rehearsal mode, MoE ensemble scoring, dashboard hardening for existing event-driven async AI judge agent
**Researched:** 2026-02-17
**Confidence:** HIGH (all findings from direct codebase analysis of `/Users/scandal/ai/arbiter/`)

## Current Architecture Summary

```
CapturePipeline (orchestrator/glue -- wires everything, contains NO business logic)
  |-- EventBus (pub/sub, asyncio.create_task dispatch, error-isolated)
  |-- DemoMachine (state machine: idle -> capturing -> paused -> stopped -> idle)
  |-- CameraCapture / AudioCapture / GeminiSession (media capture hardware)
  |-- DefensePipeline (OCR scan, injection detection, sanitization)
  |-- CommentaryPipeline (Gemini generation + Groq fallback, Cartesia TTS, display)
  |-- ScoringPipeline (single-model or MoE, theatrical reveal sequence)
  |-- DeliberationPipeline (memory persistence, cross-demo comparative ranking)
  |-- WebOperator / OperatorCLI / TUI (operator interfaces)
  |-- DisplayServer (FastAPI + WebSocket broadcast to audience + operator)
```

### Architectural Invariants (must preserve)

1. **EventBus is the only inter-pipeline coupling** -- pipelines never call each other directly
2. **Uniform wiring: each pipeline has `setup(event_bus)`** for subscription registration
3. **LLM client isolation (SCORE-03)** -- scoring, commentary, deliberation each own separate clients
4. **Error isolation** -- `EventBus._safe_call` catches all subscriber exceptions
5. **All events extend `CaptureEvent`** -- typed Pydantic models with `event_type` discriminator
6. **Provider empty-string contract** -- `LLMProvider.generate()` returns `""` on failure, never raises
7. **Module-level singletons** -- `default_bus`, `default_health`, `GeminiRateLimiter.default()`

### Current Event Chain

```
demo_started ---------> DefensePipeline resets, Camera/Audio/Gemini start
key_frame_detected ---> DefensePipeline OCR scan
transcript_received --> DefensePipeline verbal scan
demo_stopped ---------> DefensePipeline sanitizes -> publishes observation_verified
observation_verified -> [parallel] ScoringPipeline.score()
                                   CommentaryPipeline.generate()
                                   DeliberationPipeline.save()
scoring_complete -----> (scorecard stored as pending)
commentary_delivered -> ScoringPipeline._reveal_score() (theatrical display sequence)
score_revealed -------> (terminal event)
deliberation_requested -> DeliberationPipeline.deliberate() (operator-triggered)
```

---

## New Feature Integration Architecture

### 1. E2E Integration Tests

**Goal:** Full pipeline integration tests exercising `demo_started` through `score_revealed` without real LLM APIs or hardware.

**Key insight:** The EventBus IS the test seam. E2E tests wire individual pipelines to the same EventBus and drive events through DemoMachine state transitions. Do NOT construct a full `CapturePipeline` -- wire the pieces directly.

#### New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `MockLLMProvider` | `tests/helpers/mock_provider.py` | Deterministic `LLMProvider` returning canned JSON |
| `EventCollector` | `tests/helpers/event_collector.py` | Subscribes via `subscribe_all`, captures events with timestamps |
| `PipelineTestHarness` | `tests/helpers/harness.py` | Wires real pipelines with mock providers, provides `run_demo()` |
| E2E test suite | `tests/test_e2e_pipeline.py` | Integration tests for full event chains |

#### MockLLMProvider Design

```python
class MockLLMProvider(LLMProvider):
    """Returns canned responses keyed by prompt substring matching."""
    def __init__(self, name: str, responses: dict[str, str]):
        self._name = name
        self._responses = responses  # substring -> response text
        self.calls: list[dict] = []  # track calls for assertions

    async def generate(self, prompt, system_prompt, **kwargs) -> str:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        for key, response in self._responses.items():
            if key in prompt:
                return response
        return ""  # matches real provider empty-on-failure contract
```

#### EventCollector Design

```python
class EventCollector:
    """Captures all events for assertion in tests."""
    def __init__(self, event_bus: EventBus):
        self.events: list[CaptureEvent] = []
        event_bus.subscribe_all(self._capture)

    async def _capture(self, event):
        self.events.append(event)

    def of_type(self, event_type: str) -> list:
        return [e for e in self.events if e.event_type == event_type]

    async def wait_for(self, event_type: str, timeout: float = 5.0):
        """Poll until event appears or timeout."""
```

#### PipelineTestHarness Design

The harness wires real DefensePipeline, ScoringPipeline, CommentaryPipeline, and DeliberationPipeline to a shared EventBus with mock I/O. Key design decisions:

- Uses real `EventBus` (never mock it -- it is trivial and deterministic)
- Uses `MockLLMProvider` instances injected into `MoEScoringEngine`
- Uses existing `FakeDisplayServer` pattern from `test_web_operator.py`
- Uses a `RehearsalGeminiSession` (see section 2) to inject canned observations into DefensePipeline
- Replaces `ScoringEngine._client` and `CommentaryGenerator._client` with mock genai responses

#### Modifications to Existing Components

| Component | Change | Rationale |
|-----------|--------|-----------|
| `ScoringEngine.__init__` | Accept optional `client` parameter (default: create new) | Injectable for testing without monkeypatch |
| `CommentaryGenerator.__init__` | Accept optional `client` parameter (default: create new) | Same pattern |
| None others | Existing constructors already accept injectable deps | DefensePipeline takes `gemini_session`, ScoringPipeline takes `moe_engine` |

**What NOT to do:**
- Do not create a separate E2E test framework or runner -- use pytest-asyncio
- Do not mock the EventBus -- test through it
- Do not monkeypatch private methods for E2E (acceptable in unit tests, not E2E)

---

### 2. Rehearsal / Dry-Run Mode

**Goal:** Replay canned demo data through the full pipeline without live camera/audio/Gemini capture. For pre-event testing and operator training.

**Key insight:** Rehearsal is a new event source that replaces the capture layer. Downstream pipelines must not know whether data came from live capture or rehearsal.

#### New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `RehearsalGeminiSession` | `src/rehearsal/fake_session.py` | Returns pre-loaded observations via `get_observations()` |
| `RehearsalRunner` | `src/rehearsal/runner.py` | Loads scenario JSON, drives DemoMachine + EventBus |
| `RehearsalConfig` | `src/rehearsal/config.py` | Data directory, timing, LLM mode (real vs mock) |
| Scenario data | `data/rehearsal/*.json` | Canned team_name, observations, transcripts, duration |
| CLI flag | `src/main.py` | `--rehearsal` and `--scenario` arguments |

#### Critical Integration Point

`DefensePipeline._on_demo_stopped` calls `self._gemini.get_observations()` to get raw observations. In rehearsal mode there is no real GeminiSession. The fix:

```python
class RehearsalGeminiSession:
    """Fake GeminiSession returning pre-loaded observations."""
    def __init__(self, observations: list[str]):
        self._observations = list(observations)

    def get_observations(self) -> list[str]:
        return self._observations

    def clear_observations(self) -> None:
        self._observations.clear()
```

This works because `DefensePipeline.__init__` already accepts `gemini_session: GeminiSession | None` as a constructor parameter. No interface changes needed.

#### Data Flow in Rehearsal Mode

```
RehearsalRunner loads scenario JSON
  |-> Sets RehearsalGeminiSession.observations = canned data
  |-> DemoMachine.send("start_demo", team_name=...)  # publishes demo_started
  |-> asyncio.sleep(simulated_duration)
  |-> DemoMachine.send("stop_demo")                   # publishes demo_stopped
      |-> DefensePipeline._on_demo_stopped
          |-> RehearsalGeminiSession.get_observations()  # returns canned data
          |-> Sanitization runs normally
          |-> publishes observation_verified
              |-> All downstream pipelines run identically to live mode
```

#### Modifications to Existing Components

| Component | Change | Rationale |
|-----------|--------|-----------|
| `src/main.py` | Add `--rehearsal` flag, `--scenario` arg | Entry point for rehearsal |
| `CapturePipeline.__init__` | When `rehearsal_mode=True`: skip camera/audio/gemini init, use RehearsalGeminiSession for DefensePipeline | Avoid hardware requirements |
| `CapturePipeline.run` | When rehearsal: use RehearsalRunner instead of operator interface | Different event source |

**Design principle:** Rehearsal replaces input, not processing. The entire downstream event chain is identical.

---

### 3. GroqProvider + MoE E2E Coverage

**Current state:** `MoEScoringEngine` exists and works with Gemini/Claude/OpenAI providers. Groq is used as a fallback in `CommentaryGenerator` and `QAGenerator` via the OpenAI-compatible API, but there is no `GroqProvider` for use in MoE scoring. The existing `test_moe_demos.py` requires real API keys.

#### New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `GroqProvider` | `src/providers/groq_provider.py` | `LLMProvider` impl using Groq's OpenAI-compatible API |

#### GroqProvider Design

```python
class GroqProvider(LLMProvider):
    """Groq LLM provider via OpenAI-compatible API (Llama 3.3 70B)."""
    _BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        self._client = AsyncOpenAI(api_key=api_key, base_url=self._BASE_URL)
        self._model = model

    @property
    def name(self) -> str:
        return f"groq:{self._model}"

    async def generate(self, prompt, system_prompt, **kw) -> str:
        try:
            return await self._call_groq(prompt, system_prompt, kw.get("temperature", 0.3), kw.get("max_tokens", 1000))
        except Exception:
            logger.exception("Groq generation failed")
            return ""  # provider contract
```

Follows the exact same pattern as `ClaudeProvider` and `OpenAIProvider` -- retry decorator, empty string on failure, tenacity for transient errors.

#### Modifications to Existing Components

| Component | Change | Rationale |
|-----------|--------|-----------|
| `src/providers/factory.py` | Add `"groq"` case returning `GroqProvider` | Unified provider creation |
| `src/capture/pipeline.py` | Add Groq to MoE provider list when `groq_api_key` set | Wire into existing MoE setup (3 lines) |
| `src/scoring/aggregator.py` | Add `"groq"` to `DEFAULT_CALIBRATION` dict | Llama tends to score generously; needs calibration |

The existing MoE wiring in `CapturePipeline.__init__` already has the pattern:
```python
if config.moe_scoring_enabled:
    providers = [create_provider("gemini", config.gemini_api_key)]
    if config.anthropic_api_key:
        providers.append(create_provider("claude", config.anthropic_api_key))
    # ADD: if config.groq_api_key:
    #          providers.append(create_provider("groq", config.groq_api_key))
```

No architectural changes needed. Pure additive.

#### Groq Calibration Note

Add to `DEFAULT_CALIBRATION` in `src/scoring/aggregator.py`:
```python
"groq": {"temperature": 1.3, "bias": -0.3},  # Llama tends generous, flatten + offset down
```

The `ScoreAggregator` already handles parse failures gracefully (provider excluded from aggregation). Llama models are less reliable at structured JSON output than Gemini/Claude/GPT-4o, so Groq may be excluded from some aggregations -- this is fine.

#### Optional: Health-Aware Provider Selection

Currently `MoEScoringEngine` always calls all providers. With `ServiceHealth` available:

```python
# In MoEScoringEngine.score() -- optional enhancement
active_providers = [
    p for p in self._providers
    if default_health.is_healthy(f"scoring:{p.name}")
]
```

Follows the same pattern used by `CommentaryPipeline` for TTS health.

---

### 4. Dashboard Hardening

**Current state:** React+Vite app, Zustand store, WebSocket with exponential backoff reconnect, 5 panels (Status, EventStream, Counters, Defense, Score). ScorePanel is a placeholder. 7 existing test files.

#### 4a. Backend Additions (`src/operator/web.py`)

| Addition | Type | Purpose |
|----------|------|---------|
| `GET /api/health` | REST | Returns `ServiceHealth.get_status()` + provider availability |
| `GET /api/scores` | REST | Returns all saved scorecards from `ScoreStore.load_all()` |
| Score event forwarding | WebSocket | Forward `scoring_complete` event data to operator clients |
| Deliberation event forwarding | WebSocket | Forward `deliberation_complete` to operator clients |
| Heartbeat in counter loop | WebSocket | Already runs every 1s, add connection health signal |

Implementation: Add REST routes in `WebOperator._register_routes()` (same FastAPI app). Add score/deliberation event serialization in `WebOperator._on_event()`.

#### 4b. Frontend Additions

| Component | Location | Purpose |
|-----------|----------|---------|
| `ScorePanel` implementation | `panels/ScorePanel.tsx` | Display real-time scoring data (currently placeholder) |
| `HealthIndicator` | `components/HealthIndicator.tsx` | Shows service health status |
| Error boundary | `components/ErrorBoundary.tsx` | Catches React render errors per-panel |
| Protocol types | `types/protocol.ts` | Add `ScoringMessage`, `HealthMessage` types |

#### 4c. Store Changes (`store/operatorStore.ts`)

Add to `OperatorState`:
```typescript
scores: Record<string, DemoScorecard>;  // team_name -> scorecard
healthStatus: Record<string, boolean>;   // service -> healthy
```

Add dispatch cases for `scoring_complete` and `health_status` message types.

#### Modifications Summary

| Component | Change | Rationale |
|-----------|--------|-----------|
| `src/operator/web.py` | Add REST endpoints, forward scoring/deliberation events | Dashboard needs data |
| `operator-dashboard/src/types/protocol.ts` | Add message types | Type safety |
| `operator-dashboard/src/store/operatorStore.ts` | Add score/health state | Store new data |
| `operator-dashboard/src/panels/ScorePanel.tsx` | Implement real score display | Currently placeholder `TODO` |

---

## Component Boundaries (with new additions)

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `EventBus` | Pub/sub message routing | All pipelines |
| `DemoMachine` | Demo lifecycle state machine | EventBus |
| `DefensePipeline` | OCR, injection detection, sanitization | EventBus, GeminiSession/RehearsalGeminiSession |
| `CommentaryPipeline` | LLM commentary, TTS, display | EventBus, DisplayServer |
| `ScoringPipeline` | Score orchestration, theatrical reveal | EventBus, ScoringEngine/MoEScoringEngine, DisplayServer |
| `MoEScoringEngine` | Multi-provider parallel scoring | LLMProvider impls (Gemini, Claude, OpenAI, **Groq**) |
| `DeliberationPipeline` | Memory, cross-demo ranking | EventBus, MemoryStore, ScoreStore, DisplayServer |
| `WebOperator` | Operator WS commands + **REST endpoints** | EventBus, DemoMachine, DisplayServer, **ScoreStore** |
| `DisplayServer` | FastAPI, WebSocket broadcast | Browser clients |
| **`GroqProvider`** (new) | Groq/Llama LLM provider | MoEScoringEngine via LLMProvider |
| **`RehearsalRunner`** (new) | Synthetic demo event source | EventBus, DemoMachine |
| **`RehearsalGeminiSession`** (new) | Mock observations source | DefensePipeline |
| **`MockLLMProvider`** (new, test) | Deterministic test provider | PipelineTestHarness |
| **`EventCollector`** (new, test) | Event capture for assertions | EventBus |
| **`PipelineTestHarness`** (new, test) | E2E test wiring | All pipelines |

---

## Patterns to Follow

### Pattern 1: Pipeline Setup Convention
All pipelines: `__init__` creates components, `setup(event_bus)` wires subscriptions. New components (RehearsalRunner) must follow this.

### Pattern 2: Provider Error Contract
Providers return `""` on failure, log internally. `GroqProvider` must follow this exactly -- `MoEScoringEngine` and fallback logic depend on it.

### Pattern 3: Event Typing
All events extend `CaptureEvent` with fixed `event_type: str` default. Any new events (e.g. `rehearsal_complete`) must follow.

### Pattern 4: Graceful Degradation via ServiceHealth
Track health in `default_health`, skip unhealthy components, retry after exponential window. Apply to MoE provider health (same pattern as TTS health in CommentaryPipeline).

### Pattern 5: Detached Tasks for Display Operations
Display pushes run as `asyncio.create_task` to never block EventBus callbacks. All existing pipelines follow this; new display operations must too.

---

## Anti-Patterns to Avoid

### Direct Pipeline-to-Pipeline Calls
Pipelines must communicate through EventBus only. The one exception is shared `DisplayServer` (broadcast channel, not business logic).

### Mocking the EventBus in E2E Tests
EventBus is trivial and deterministic. Mocking it hides real routing bugs. Use real EventBus + EventCollector.

### Global Mutable State for Test/Live Switching
Do not use env vars or module globals to toggle behavior inside pipeline code. Inject dependencies via constructor (DefensePipeline already does this with `gemini_session` parameter).

### Monkeypatching Internals in E2E Tests
Use constructor injection (MockLLMProvider, RehearsalGeminiSession) instead of patching private methods like `_call_gemini`.

---

## Suggested Build Order

### Phase 1: GroqProvider (smallest, self-contained)
1. Create `src/providers/groq_provider.py`
2. Add `"groq"` to `src/providers/factory.py`
3. Add calibration to `src/scoring/aggregator.py`
4. Add to `CapturePipeline` MoE wiring (3 lines)
5. Unit tests
**Why first:** Minimal scope, no dependencies on other new features, unblocks MoE E2E testing.

### Phase 2: E2E Test Infrastructure
1. Create `tests/helpers/mock_provider.py`
2. Create `tests/helpers/event_collector.py`
3. Create `tests/helpers/harness.py` (includes RehearsalGeminiSession)
4. Write E2E: happy path `demo_started` -> `score_revealed`
5. Write E2E: MoE with 3 mock providers (including mock Groq)
6. Write E2E: provider failure + fallback
7. Write E2E: full lifecycle with state machine transitions
**Why second:** Validates all existing code + GroqProvider, catches regressions before more features.

### Phase 3: Rehearsal Mode
1. Create `src/rehearsal/` package (runner, config, fake_session)
2. Create scenario JSON files in `data/rehearsal/`
3. Add `--rehearsal` flag to `src/main.py`
4. Modify `CapturePipeline` to skip hardware in rehearsal
5. E2E test for rehearsal mode (reuses test infrastructure from Phase 2)
**Why third:** Depends on E2E infra. Rehearsal IS a persistent E2E harness for operators.

### Phase 4: Dashboard Hardening
1. Backend: health endpoint, score REST endpoints, event forwarding
2. Frontend: implement ScorePanel, add HealthIndicator, error boundaries
3. Frontend tests for new panels
**Why last:** No downstream dependencies, benefits from all pipeline work being complete.

---

## Sources

- All findings from direct analysis of Arbiter codebase at `/Users/scandal/ai/arbiter/`
- Key files examined: `src/capture/event_bus.py`, `src/capture/pipeline.py`, `src/scoring/pipeline.py`, `src/scoring/moe_engine.py`, `src/scoring/aggregator.py`, `src/providers/base.py`, `src/providers/factory.py`, `src/providers/gemini_provider.py`, `src/providers/claude_provider.py`, `src/providers/openai_provider.py`, `src/operator/web.py`, `src/commentary/pipeline.py`, `src/commentary/generator.py`, `src/defense/pipeline.py`, `src/memory/pipeline.py`, `src/resilience/health.py`, `src/resilience/retry.py`, `src/capture/config.py`, `src/capture/models.py`, `src/scoring/models.py`, `src/defense/models.py`, `src/main.py`, all test files, operator dashboard source
- Confidence: HIGH -- recommendations follow patterns already established in the codebase
