# Phase 8: E2E Pipeline Coverage - Research

**Researched:** 2026-02-17
**Domain:** End-to-end async event pipeline testing (pytest, asyncio, mock providers)
**Confidence:** HIGH

## Summary

Phase 8 builds E2E tests on top of the Phase 7 test infrastructure (EventCollector, singleton reset, pytest-timeout, asyncio_mode=auto). The arbiter project has a well-defined event pipeline: `DemoMachine` publishes lifecycle events through `EventBus`, which triggers cascading async handlers across four sub-pipelines (Defense, Commentary, Scoring, Deliberation). Each sub-pipeline subscribes via `setup(event_bus)` and publishes downstream events via `asyncio.create_task`. The full chain is: `demo_started` -> capture events -> `demo_stopped` -> `observation_verified` -> (parallel: commentary + scoring + deliberation memory save) -> `commentary_delivered` -> score reveal -> `scoring_complete` -> `score_revealed`.

The codebase already has 373 unit tests covering individual pipeline components, but NO test drives the full chain end-to-end. The `CapturePipeline.run()` method wires 8 direct subscriptions plus 4 sub-pipeline `setup()` calls (defense, commentary, scoring, deliberation), totaling 22 EventBus subscriptions. These wiring connections are the primary regression risk -- a typo in an event name string would silently break the pipeline with no test catching it.

The MoE scoring engine has unit tests with mock providers (`test_scoring_aggregator.py`) but has never been tested through the full `ScoringPipeline` event path with multiple mock providers returning different scores and `ScoreAggregator` producing weighted results. The `EventCollector` from Phase 7 is the key tool for all E2E assertions -- it provides deterministic `wait_for(event_type)` that handles the `asyncio.create_task` dispatch pattern used by `EventBus.publish()`.

**Primary recommendation:** Write four test files matching the four requirements (E2E-01 through E2E-04), all using real `EventBus` instances + `EventCollector` for assertions, with mock/stub replacements only for external I/O (LLM calls, TTS, display server, OCR, file I/O). No new production code is needed.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=9.0.2 | Test framework | Already installed, all 373 existing tests use it |
| pytest-asyncio | >=0.23 | Async test support with `asyncio_mode=auto` | Already configured in pyproject.toml |
| pytest-timeout | ~2.4 | Kill hanging async tests at 30s | Already configured from Phase 7 |
| unittest.mock | stdlib | AsyncMock, MagicMock, patch for mocking LLM/I/O | Used extensively in existing tests |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| EventCollector | custom (Phase 7) | Deterministic async event assertion | Every E2E test that publishes events and asserts downstream effects |
| pytest-xdist | ~3.8 | Parallel test execution | E2E tests must be xdist-compatible (use fresh EventBus per test) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Mock LLM providers | VCR.py cassettes | Cassettes add complexity; mocks give full control over scores. Use mocks for E2E, cassettes for integration tests in Phase 9 |
| Real EventBus + EventCollector | Mock EventBus | Mocking EventBus hides real routing bugs -- the exact bugs E2E tests should catch |
| Individual test files per requirement | Single monolithic test file | Separate files allow parallel execution and clear requirement traceability |

## Architecture Patterns

### Recommended Test Structure

```
tests/
    conftest.py                    # EXISTING: singleton reset, event_bus, event_collector, VCR
    helpers/
        __init__.py                # EXISTING
        event_collector.py         # EXISTING: EventCollector class
    test_e2e_pipeline_chain.py     # NEW: E2E-01 full pipeline chain
    test_e2e_moe_scoring.py        # NEW: E2E-02 MoE integration through pipeline
    test_e2e_event_wiring.py       # NEW: E2E-03 subscription wiring regression
    test_e2e_task_draining.py      # NEW: E2E-04 multi-level create_task chains
```

### Pattern 1: Full Pipeline Chain Test (E2E-01)

**What:** Drive a synthetic demo through the entire pipeline by mocking all external I/O (Gemini session, OCR, TTS, display, LLM providers) and asserting events fire in the correct order.

**When to use:** Validates the wiring between all sub-pipelines through the event bus.

**Key insight:** The `CapturePipeline` constructor requires a `CaptureConfig` and creates real hardware components (CameraCapture, AudioCapture, GeminiSession). For E2E testing, we do NOT instantiate `CapturePipeline` directly. Instead, we replicate its `setup()` wiring with the individual sub-pipelines (Defense, Commentary, Scoring, Deliberation) sharing a single `EventBus`, then drive events manually.

**Why not use CapturePipeline directly:** It requires a real CaptureConfig with API keys, creates OpenCV camera handles, PyAudio streams, and Gemini WebSocket sessions. Mocking all of those is fragile and tests the mocks, not the pipeline wiring. The sub-pipelines are the testable unit -- they accept an EventBus and subscribe to events.

**Example approach:**
```python
async def test_full_pipeline_chain(event_bus, event_collector):
    """Drive synthetic demo through defense -> commentary -> scoring -> deliberation."""
    # Create sub-pipelines with mocked external dependencies
    defense = DefensePipeline(api_key="test", gemini_session=mock_gemini)
    commentary = CommentaryPipeline(...)  # mock TTS, display
    scoring = ScoringPipeline(api_key="test", display=mock_display)
    deliberation = DeliberationPipeline(api_key="test", display=mock_display, ...)

    # Wire all pipelines (replicates CapturePipeline.run() wiring)
    await defense.setup(event_bus)
    await commentary.setup(event_bus)
    await scoring.setup(event_bus)
    await deliberation.setup(event_bus)

    # Mock LLM calls inside each pipeline
    # ...

    # Drive the pipeline: publish demo_stopped (triggers defense sanitization)
    event_bus.publish(DemoStopped(team_name="TestTeam", duration=180.0))

    # Assert events fire in order
    await event_collector.wait_for("observation_verified")
    await event_collector.wait_for("scoring_complete")
    await event_collector.wait_for("commentary_delivered")

    # Verify order
    types = [e.event_type for e in event_collector.events]
    obs_idx = types.index("observation_verified")
    score_idx = types.index("scoring_complete")
    assert obs_idx < score_idx
```

**Critical detail about DefensePipeline._on_demo_stopped:** This handler is the gateway -- it sanitizes observations and publishes `observation_verified`. For it to produce output, the defense pipeline needs a mock GeminiSession with `get_observations()` returning test data. The defense pipeline's `_on_demo_started` must also have been called first to set `_current_team`.

### Pattern 2: MoE Integration Through Pipeline (E2E-02)

**What:** Wire 3 mock LLM providers into a real `MoEScoringEngine`, connect it to a real `ScoringPipeline`, and drive an `observation_verified` event through. Assert `ScoreAggregator` produces a weighted result.

**When to use:** Validates the MoE path that is wired but has never been tested through the full pipeline event path.

**Key insight:** The existing `test_scoring_aggregator.py::TestMoEScoringEngine` tests mock providers but calls `engine.score()` directly. E2E-02 tests the path: `observation_verified` event -> `ScoringPipeline._on_observation_verified` -> selects `_moe_engine` -> `MoEScoringEngine.score()` -> parallel provider calls -> `ScoreAggregator.aggregate_criterion()` -> `ScoringComplete` event published.

**Example approach:**
```python
def _make_provider(name: str, scores: dict[str, float]) -> MagicMock:
    """Create mock LLMProvider returning specific criterion scores."""
    provider = MagicMock()
    type(provider).name = PropertyMock(return_value=name)
    response = json.dumps({"criteria": [
        {"name": n, "score": s, "justification": f"Evidence for {n}"}
        for n, s in scores.items()
    ]})
    provider.generate = AsyncMock(return_value=response)
    return provider

async def test_moe_three_providers_through_pipeline(event_bus, event_collector):
    providers = [
        _make_provider("gemini", {"Technical Execution": 8.0, "Innovation": 7.0, "Demo Quality": 6.0}),
        _make_provider("claude", {"Technical Execution": 7.0, "Innovation": 8.0, "Demo Quality": 7.0}),
        _make_provider("openai", {"Technical Execution": 9.0, "Innovation": 6.0, "Demo Quality": 5.0}),
    ]
    moe = MoEScoringEngine(providers=providers)
    pipeline = ScoringPipeline(api_key="test", display=mock_display, moe_engine=moe)
    pipeline._store.save = AsyncMock()
    await pipeline.setup(event_bus)

    event_bus.publish(ObservationVerified(output=sanitized))
    scoring_event = await event_collector.wait_for("scoring_complete")

    # Assert aggregated score is between min and max provider scores
    scorecard = scoring_event.scorecard
    assert scorecard.total_score > 0
    assert all(p.generate.called for p in providers)
```

### Pattern 3: Event Wiring Regression (E2E-03)

**What:** Verify that every `subscribe()` call made during pipeline setup is actually connected and responsive.

**When to use:** Catches string typo regressions (e.g., `"observation_verifed"` vs `"observation_verified"`).

**Key insight:** There are exactly 22 EventBus subscriptions wired across the system. The test should:
1. Enumerate all expected (event_type, pipeline) pairs
2. For each, publish a minimal event of that type
3. Assert the subscription handler was called (or the EventCollector captured a downstream event)

**Complete subscription inventory from codebase analysis:**

| Pipeline | Event Type | Handler | Source File:Line |
|----------|-----------|---------|-----------------|
| CapturePipeline | demo_started | _on_demo_started | pipeline.py:263 |
| CapturePipeline | demo_stopped | _on_demo_stopped | pipeline.py:264 |
| CapturePipeline | demo_paused | _on_demo_paused | pipeline.py:267 |
| CapturePipeline | demo_resumed | _on_demo_resumed | pipeline.py:268 |
| CapturePipeline | key_frame_detected | _on_key_frame | pipeline.py:271 |
| CapturePipeline | transcript_received | _on_transcript | pipeline.py:272 |
| CapturePipeline | tts_speaking | _on_tts_speaking | pipeline.py:278 |
| CapturePipeline | tts_finished | _on_tts_finished | pipeline.py:279 |
| DefensePipeline | key_frame_detected | _on_key_frame | defense/pipeline.py:114 |
| DefensePipeline | transcript_received | _on_transcript | defense/pipeline.py:115 |
| DefensePipeline | demo_started | _on_demo_started | defense/pipeline.py:116 |
| DefensePipeline | demo_stopped | _on_demo_stopped | defense/pipeline.py:117 |
| CommentaryPipeline | observation_verified | _on_observation_verified | commentary/pipeline.py:105 |
| CommentaryPipeline | qa_requested | _on_qa_requested | commentary/pipeline.py:106 |
| CommentaryPipeline | injection_detected | _on_injection_detected | commentary/pipeline.py:107 |
| CommentaryPipeline | demo_started | _on_demo_started | commentary/pipeline.py:108 |
| CommentaryPipeline | demo_stopped | _on_demo_stopped | commentary/pipeline.py:109 |
| ScoringPipeline | observation_verified | _on_observation_verified | scoring/pipeline.py:57 |
| ScoringPipeline | commentary_delivered | _on_commentary_delivered | scoring/pipeline.py:58 |
| DeliberationPipeline | observation_verified | _on_observation_verified | memory/pipeline.py:74 |
| DeliberationPipeline | deliberation_requested | _on_deliberation_requested | memory/pipeline.py:75 |
| CapturePipeline (global) | * (all events) | _log_event | pipeline.py:275 (subscribe_all) |

**Testing approach for CapturePipeline subscriptions:** Since CapturePipeline requires heavy hardware dependencies, test its subscription wiring by inspecting `event_bus._subscribers` after calling the sub-pipeline `setup()` methods. For the 8 CapturePipeline-specific subscriptions (demo lifecycle, key_frame, transcript, tts), either:
- (a) Test them through a lightweight mock CapturePipeline that only runs the `run()` subscription block, OR
- (b) Test them indirectly by verifying the sub-pipelines respond to their trigger events (defense responds to demo_stopped, etc.) and document that CapturePipeline subscriptions are covered by unit tests in existing test files.

**Recommended:** Option (b) is pragmatic. The 4 sub-pipeline `setup()` calls are the high-value wiring to verify. The 8 CapturePipeline-direct subscriptions are simple forwarding handlers (e.g., `_on_key_frame` just appends to session) already covered by unit tests.

### Pattern 4: Multi-Level Task Draining (E2E-04)

**What:** Test that multi-step async chains triggered by `asyncio.create_task` inside EventBus handlers fully complete before assertions.

**When to use:** Validates the EventCollector correctly handles chained events where handler A publishes event B which triggers handler C.

**Key insight:** The real chain is: `observation_verified` -> `ScoringPipeline._on_observation_verified()` calls `engine.score()` then publishes `ScoringComplete` via `event_bus.publish()` which uses `asyncio.create_task()`. This is a two-level chain:
- Level 1: EventBus dispatches `observation_verified` handlers via `create_task`
- Level 2: Inside the handler, `event_bus.publish(ScoringComplete(...))` dispatches another `create_task`

The EventCollector's `wait_for()` handles this naturally because it uses `asyncio.Event` which gets set whenever the target event appears, regardless of task nesting depth. But we need to VERIFY this behavior works correctly.

**Another real chain:** `observation_verified` -> commentary pipeline generates text -> publishes `commentary_delivered` -> scoring pipeline's `_on_commentary_delivered` pops scorecard -> launches `_reveal_score` as detached task -> reveal publishes `score_revealed`. This is a THREE-level chain.

### Anti-Patterns to Avoid

- **Instantiating CapturePipeline in tests:** Requires CaptureConfig with real API keys and creates hardware handles. Test the sub-pipelines directly.
- **Mocking EventBus:** The EventBus is 50 lines of trivial code. Using a real EventBus catches real wiring bugs. Mock the HANDLERS' dependencies, not the bus.
- **Testing event names with string constants:** Don't define `EVENT_OBSERVATION_VERIFIED = "observation_verified"` in tests. Use the event model classes directly (e.g., `ObservationVerified(...)` which has `event_type = "observation_verified"` as a class default). This catches model-level typos.
- **Using `asyncio.sleep()` for draining:** Use `EventCollector.wait_for()` for all event assertions. The only acceptable sleep is `asyncio.sleep(0)` as a single yield to let tasks run when NOT using EventCollector (but prefer EventCollector).
- **Forgetting to call `setup()`:** Each sub-pipeline requires `await pipeline.setup(event_bus)` to subscribe. Missing this call means the pipeline silently ignores all events.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async event assertion | `asyncio.sleep()` polling loops | `EventCollector.wait_for()` | Deterministic, fast, handles multi-level chains |
| Mock LLM providers | Custom provider classes | `MagicMock` with `AsyncMock(return_value=json_response)` | Existing pattern in test_scoring_aggregator.py works perfectly |
| Event ordering assertion | Manual index tracking | `event_collector.events` list + index comparison | EventCollector captures all events in order |
| Mock display server | Custom stub class | `MagicMock(spec=DisplayServer)` with `AsyncMock` methods | Existing pattern in test_scoring_pipeline.py and test_deliberation_pipeline.py |
| Subscription inventory | Hardcoded list of strings | Inspect `event_bus._subscribers` dict after setup | Catches additions/removals automatically |

**Key insight:** Almost all mock patterns needed for E2E tests already exist in the current test suite. The scoring pipeline tests mock DisplayServer, the aggregator tests mock LLMProviders, the deliberation tests mock MemoryStore/ScoreStore. E2E tests compose these existing patterns.

## Common Pitfalls

### Pitfall 1: Defense Pipeline Requires Demo Lifecycle Setup

**What goes wrong:** Publishing `demo_stopped` directly without first calling `_on_demo_started` leaves `_current_team` as empty string and `_transcripts`/`_roasts` in stale state.

**Why it happens:** DefensePipeline._on_demo_started resets state (`_current_team`, `_roasts`, `_transcripts`, cooldown, logger). Without it, the pipeline operates on stale data from a previous test.

**How to avoid:** In full chain tests, always publish `demo_started` first, yield to event loop, then publish `demo_stopped`. Or call `defense._on_demo_started(DemoStarted(...))` directly.

**Warning signs:** Empty team names in sanitized output, stale injection attempts from previous tests.

### Pitfall 2: Commentary Pipeline Requires TTS Connect and Display Start

**What goes wrong:** `CommentaryPipeline.setup()` calls `await self._tts.connect()` and `await self._display.start()`. These hit real network services (Cartesia API, uvicorn HTTP server).

**Why it happens:** The setup method initializes external connections as part of wiring.

**How to avoid:** Mock/patch `_tts.connect()` and `_display.start()` as AsyncMock before calling `setup()`. Or create the CommentaryPipeline with mocked internals. The existing test_commentary_generator.py shows how to mock the Gemini stream and Groq client.

**Warning signs:** `ConnectionRefusedError` or `CARTESIA_API_KEY not set` warnings during E2E tests.

### Pitfall 3: GeminiSession Mock for Defense Pipeline

**What goes wrong:** DefensePipeline._on_demo_stopped calls `self._gemini.get_observations()` to get raw observations for sanitization. If `_gemini` is None, `raw_observations` is empty and `observation_verified` is published with empty observations.

**Why it happens:** The pipeline gracefully handles None gemini_session (returns empty observations), but this means downstream pipelines receive no data to work with.

**How to avoid:** Create a mock GeminiSession with `get_observations()` returning test observation strings. Pass it to DefensePipeline constructor.

**Warning signs:** Tests pass but all downstream events have empty observation data.

### Pitfall 4: Event Ordering Non-Determinism with Parallel Subscribers

**What goes wrong:** When `observation_verified` is published, THREE subscribers fire in parallel (Commentary, Scoring, Deliberation). The order in which their handlers complete is non-deterministic.

**Why it happens:** EventBus.publish() iterates subscribers in registration order, but each callback runs as an independent `asyncio.create_task()`. Task execution order depends on the event loop scheduler.

**How to avoid:** Do NOT assert a specific order between parallel subscribers (e.g., don't assert scoring_complete comes before commentary_delivered). Assert that ALL expected events fire, and only assert ordering for causally dependent events (e.g., `observation_verified` BEFORE `scoring_complete`).

**Warning signs:** Tests that pass 99% of the time but occasionally fail on ordering assertions.

### Pitfall 5: ScoringPipeline Score Reveal Is a Detached Task

**What goes wrong:** `_on_commentary_delivered` launches `_reveal_score` as `asyncio.create_task()`. The reveal includes `asyncio.sleep(2.0)` pauses for theatrical timing. Tests waiting for `score_revealed` event must account for these delays.

**Why it happens:** The reveal is intentionally async and detached to not block the event bus callback.

**How to avoid:** For E2E tests, either (a) mock the sleep calls to be instant, or (b) use a longer timeout on `event_collector.wait_for("score_revealed", timeout=15.0)`. Option (a) is cleaner -- patch `asyncio.sleep` to return immediately within the scoring pipeline reveal.

**Warning signs:** Tests timing out waiting for `score_revealed` event.

### Pitfall 6: Commentary Pipeline Stream Generator

**What goes wrong:** CommentaryPipeline._on_observation_verified uses `async for sentence, emotion, i in self._generator.stream_sentences(event.output)` which is an async generator hitting Gemini's streaming API.

**Why it happens:** The streaming generator is the primary code path (Groq batch and static are fallbacks).

**How to avoid:** Mock `self._generator.stream_sentences` to be an async generator yielding test sentences. Or mock `self._generator._client.aio.models.generate_content_stream` to return a fake async iterator (existing pattern in test_commentary_generator.py).

**Warning signs:** Tests hanging on `await event_collector.wait_for("commentary_delivered")` because the generator is trying to call real Gemini.

## Code Examples

### Mock GeminiSession for Defense Pipeline

```python
from unittest.mock import MagicMock

def make_mock_gemini(observations: list[str]) -> MagicMock:
    """Create a mock GeminiSession that returns canned observations."""
    gemini = MagicMock()
    gemini.get_observations.return_value = observations
    gemini.clear_observations = MagicMock()
    return gemini
```

### Mock Commentary Generator Stream

```python
from unittest.mock import AsyncMock, MagicMock, patch

async def fake_stream_sentences(sanitized):
    """Async generator yielding (sentence, emotion, index) tuples."""
    sentences = ["Bold strategy.", "The code is solid."]
    for i, s in enumerate(sentences):
        yield s, "sarcastic", i

# Usage: patch commentary._generator.stream_sentences
commentary._generator.stream_sentences = fake_stream_sentences
```

### Mock LLM Provider with Specific Scores

```python
from unittest.mock import AsyncMock, MagicMock, PropertyMock
import json

def make_mock_provider(name: str, scores: dict[str, float]) -> MagicMock:
    """Create a mock LLMProvider returning JSON with specific criterion scores."""
    provider = MagicMock()
    type(provider).name = PropertyMock(return_value=name)
    response = json.dumps({
        "criteria": [
            {"name": n, "score": s, "justification": f"Evidence for {n}"}
            for n, s in scores.items()
        ]
    })
    provider.generate = AsyncMock(return_value=response)
    return provider
```

### Event Ordering Assertion Pattern

```python
async def test_event_ordering(event_bus, event_collector):
    # ... setup pipelines, mock dependencies ...

    event_bus.publish(DemoStopped(team_name="Team", duration=180.0))

    # Wait for the final event in the chain
    await event_collector.wait_for("scoring_complete", timeout=5.0)

    # Assert causal ordering (not parallel ordering)
    types = [e.event_type for e in event_collector.events]
    assert types.index("observation_verified") < types.index("scoring_complete")
```

### Subscription Wiring Verification Pattern

```python
async def test_defense_subscriptions_connected(event_bus):
    defense = DefensePipeline(api_key="test")
    await defense.setup(event_bus)

    expected = {"key_frame_detected", "transcript_received", "demo_started", "demo_stopped"}
    actual = set(event_bus._subscribers.keys())
    assert expected.issubset(actual)

    # Verify handlers are responsive (not just registered)
    defense._on_demo_started = AsyncMock()
    event_bus.publish(DemoStarted(team_name="Test"))
    await asyncio.sleep(0)
    defense._on_demo_started.assert_called_once()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `asyncio.sleep(0)` for event draining | EventCollector.wait_for() | Phase 7 (2026-02-17) | Deterministic, handles multi-level chains |
| No singleton isolation | Autouse conftest fixture | Phase 7 (2026-02-17) | Tests can run in parallel |
| Individual pipeline unit tests only | E2E chain tests across pipelines | Phase 8 (this phase) | Catches wiring regressions between pipelines |

## Open Questions

1. **Whether to test CapturePipeline direct subscriptions in E2E-03**
   - What we know: CapturePipeline.run() wires 8 direct subscriptions (demo lifecycle, key_frame, transcript, TTS). These are simple forwarding handlers.
   - What's unclear: Whether to replicate the full CapturePipeline subscription block in E2E tests or just test the 4 sub-pipeline setups.
   - Recommendation: Test the 4 sub-pipeline `setup()` wiring (14 subscriptions across defense/commentary/scoring/deliberation) as the high-value targets. The 8 CapturePipeline-direct subscriptions are covered by existing unit tests and are simple pass-through handlers. Document this scoping decision in the test file.

2. **CommentaryPipeline.setup() side effects**
   - What we know: `setup()` calls `_tts.connect()` and `_display.start()` which hit external services.
   - What's unclear: Best way to isolate these in E2E tests -- mock before setup, or restructure setup.
   - Recommendation: Patch `_tts.connect` and `_display.start` as AsyncMock before calling setup. This is the standard mock pattern and avoids production code changes. Alternatively, create CommentaryPipeline with pre-mocked internals (`_tts = MagicMock()`, `_display = MagicMock()`).

3. **Score reveal theatrical timing in E2E tests**
   - What we know: `_reveal_score` has `asyncio.sleep(2.0)` and `asyncio.sleep(1.5)` calls for theatrical pacing.
   - What's unclear: Whether to mock these sleeps or use longer timeouts.
   - Recommendation: Patch `asyncio.sleep` within the scoring pipeline module to return instantly during E2E tests. This keeps tests fast (sub-second) while testing the full reveal flow.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis: all source files in `src/capture/`, `src/defense/`, `src/commentary/`, `src/scoring/`, `src/memory/`
- Direct codebase analysis: all 18 test files in `tests/`
- Phase 7 research and verification: `.planning/phases/07-test-infrastructure/07-RESEARCH.md`, `07-VERIFICATION.md`
- EventCollector implementation: `tests/helpers/event_collector.py`
- conftest.py implementation: `tests/conftest.py`

### Secondary (MEDIUM confidence)
- pytest-asyncio auto mode behavior with nested create_task chains (verified by Phase 7 test runs)
- EventBus.publish() -> asyncio.create_task() sequencing (verified by existing test patterns using asyncio.sleep(0))

### Tertiary (LOW confidence)
- None. All findings are derived from direct codebase analysis.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All tools already installed and configured from Phase 7
- Architecture patterns: HIGH -- All patterns derived from direct analysis of existing source code and test patterns
- Pitfalls: HIGH -- Identified from reading actual handler implementations and their dependencies
- Event chain mapping: HIGH -- Complete subscription inventory from grep of all subscribe() calls

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (stable codebase, no external dependencies changing)
