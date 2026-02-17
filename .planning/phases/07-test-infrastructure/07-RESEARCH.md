# Phase 7: Test Infrastructure - Research

**Researched:** 2026-02-17
**Domain:** Python test infrastructure (pytest ecosystem, async testing, HTTP recording)
**Confidence:** HIGH

## Summary

Phase 7 establishes the test infrastructure foundation that all subsequent v1.1 phases depend on. The arbiter project has 373 tests across 13 test files, all using pytest 9.x + pytest-asyncio 1.3.0 with Python 3.13. The codebase has three module-level singletons (`default_bus`, `default_health`, `GeminiRateLimiter._instance`) that leak state between tests, an event bus that uses `asyncio.create_task` for fire-and-forget delivery (requiring `await asyncio.sleep(0)` hacks in tests), and zero test markers for separating unit from integration tests. There is no `conftest.py`, no pytest configuration in `pyproject.toml`, and no timeout guards.

The standard stack is well-established: pytest-timeout for hang prevention, pytest-xdist for parallel execution, VCR.py + pytest-recording for HTTP cassette recording. VCR.py 8.1.1 rewrote its httpx support to patch httpcore directly, which is directly compatible with google-genai's httpx-based transport (confirmed: google-genai 1.63.0 uses `httpx 0.28.1` as its default async HTTP client, with no aiohttp installed in this project). The EventCollector pattern (subscribe_all + async wait_for) replaces the 80+ `asyncio.sleep()` calls scattered across test files.

**Primary recommendation:** Create a `tests/conftest.py` with autouse singleton reset fixture, EventCollector fixture, and pytest-timeout/xdist/VCR configuration in `pyproject.toml`. This is pure additive work -- zero production code changes required.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest-timeout | 2.4.0 | Kill hanging async tests after configurable deadline | Declarative `timeout = 30` in pyproject.toml. No code changes needed. Released May 2025, supports Python 3.13. Compatible with pytest 9 and pytest-asyncio 1.3.0. |
| pytest-xdist | 3.8.0 | Distribute tests across CPU cores | `pytest -n auto` auto-detects cores. Each worker gets its own event loop -- no shared state issues when singletons are properly reset. Released July 2025, supports Python 3.13. |
| vcrpy | 8.1.1 | Record/replay HTTP interactions to YAML cassettes | Patches httpcore (not httpx directly) since v8.0.0. Supports httpx 0.28.x async. Released Jan 2026. Supports Python 3.10-3.13. |
| pytest-recording | 0.13.4 | Pytest integration for VCR.py (`@pytest.mark.vcr`) | Thin wrapper providing `vcr_config` fixture and `--record-mode` CLI flag. Released May 2025. Supports Python 3.9-3.13. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| filelock | >=3.0 | Session-scoped fixture synchronization for xdist workers | Only if session-scoped fixtures need cross-worker coordination (e.g., shared test data). Likely not needed since all fixtures are function-scoped. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-timeout | `asyncio.wait_for()` wrappers | Boilerplate in every test; pytest-timeout is declarative and global |
| pytest-xdist | pytest-parallel | Abandoned 2020, no asyncio support |
| VCR.py + pytest-recording | respx | Mocks httpx transport directly; too coupled to SDK internals |
| VCR.py + pytest-recording | manual fixture files | VCR gives deterministic replay without hand-authoring cassette data |
| EventCollector (custom) | anyio testing utils | Project is pure asyncio; adding anyio creates confusion |

**Installation:**
```bash
# Update pyproject.toml [dependency-groups] dev section, then:
uv sync --group dev
```

## Architecture Patterns

### Recommended Project Structure

```
tests/
    conftest.py              # NEW: autouse singleton reset, EventCollector fixture, VCR config
    helpers/
        __init__.py
        event_collector.py   # NEW: EventCollector class with wait_for()
    cassettes/               # NEW: VCR.py recorded HTTP cassettes (YAML)
    test_commentary_generator.py
    test_deliberation_engine.py
    test_deliberation_models.py
    test_deliberation_pipeline.py
    test_memory_store.py
    test_moe_demos.py
    test_qa.py
    test_rate_limiter.py
    test_scoring_aggregator.py
    test_scoring_engine.py
    test_scoring_pipeline.py
    test_scoring_rubric.py
    test_scoring_store.py
    test_tui.py
    test_web_operator.py
```

### Pattern 1: Singleton Reset Autouse Fixture

**What:** An autouse conftest.py fixture that resets all three module-level singletons between every test.

**When to use:** Always (autouse). Prevents state leakage between tests and between xdist workers.

**Why critical:** The codebase has exactly three singletons that leak state:
1. `default_bus` in `src/capture/event_bus.py` (line 97) -- module-level `EventBus()` instance. `DemoMachine.__init__` defaults to it. Subscribers from one test persist into the next.
2. `default_health` in `src/resilience/health.py` (line 78) -- module-level `ServiceHealth()` instance. `CommentaryPipeline` uses it directly (14 references in `commentary/pipeline.py`). `test_qa.py` mutates it without cleanup (6 calls to `mark_unhealthy`/`mark_healthy`).
3. `GeminiRateLimiter._instance` in `src/resilience/rate_limiter.py` (line 24) -- class-level singleton. `test_rate_limiter.py` already resets it with a local autouse fixture (line 25-27), but no other test file does.

**Example:**
```python
# tests/conftest.py
import pytest

from src.capture.event_bus import EventBus, default_bus
from src.resilience.health import ServiceHealth, default_health
from src.resilience.rate_limiter import GeminiRateLimiter
import src.capture.event_bus as event_bus_module
import src.resilience.health as health_module


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset all module-level singletons between tests.

    Prevents state leakage from: subscriber lists on default_bus,
    health records on default_health, and the GeminiRateLimiter instance.
    """
    # Reset default_bus: clear all subscribers
    event_bus_module.default_bus = EventBus()

    # Reset default_health: fresh ServiceHealth
    health_module.default_health = ServiceHealth()

    # Reset GeminiRateLimiter singleton
    GeminiRateLimiter._instance = None

    yield

    # Post-test cleanup (same reset to be safe)
    event_bus_module.default_bus = EventBus()
    health_module.default_health = ServiceHealth()
    GeminiRateLimiter._instance = None
```

**Critical detail:** Simply clearing subscribers is not enough -- code that imports `from src.capture.event_bus import default_bus` gets a reference to the original object. The reset must either (a) replace the module attribute so future imports get the new object, or (b) mutate the existing object in-place. Option (a) is safer because `DemoMachine.__init__` does `event_bus or default_bus` at construction time, fetching the module attribute each time. But `test_qa.py` imports `default_health` locally inside test methods (`from src.resilience.health import default_health`), which re-reads the module attribute. So replacing the module attribute works correctly for both patterns.

### Pattern 2: EventCollector with Async wait_for()

**What:** A test helper that subscribes to all EventBus events and provides deterministic async assertion via `wait_for(event_type, timeout)` instead of `asyncio.sleep()`.

**When to use:** Any test that publishes events via `EventBus.publish()` and needs to assert on downstream effects delivered by `asyncio.create_task`.

**Why critical:** The EventBus dispatches subscriber callbacks via `asyncio.create_task()` (line 77 of `event_bus.py`). Tests cannot simply publish and then assert -- the task hasn't run yet. The current codebase uses two workaround patterns:
1. `await asyncio.sleep(0)` -- yields to event loop once, works when subscriber is fast (used 5 times in scoring/deliberation pipeline tests)
2. `await asyncio.sleep(0.1)` or `await asyncio.sleep(SLEEP)` -- arbitrary delay, flaky and slow (used 80+ times in `test_tui.py`, a few times in `test_scoring_pipeline.py`)

**Example:**
```python
# tests/helpers/event_collector.py
import asyncio
from src.capture.models import CaptureEvent
from src.capture.event_bus import EventBus


class EventCollector:
    """Captures events from EventBus for deterministic test assertion.

    Register via event_bus.subscribe_all(collector). Then use
    wait_for(event_type) to wait for a specific event instead of
    arbitrary sleep.
    """

    def __init__(self, event_bus: EventBus):
        self.events: list[CaptureEvent] = []
        self._waiters: dict[str, asyncio.Event] = {}
        event_bus.subscribe_all(self._on_event)

    async def _on_event(self, event: CaptureEvent) -> None:
        self.events.append(event)
        if event.event_type in self._waiters:
            self._waiters[event.event_type].set()

    async def wait_for(self, event_type: str, timeout: float = 5.0) -> CaptureEvent:
        """Wait until an event of the given type is captured, or timeout.

        If the event has already been captured, returns immediately.
        """
        # Check if already captured
        existing = [e for e in self.events if e.event_type == event_type]
        if existing:
            return existing[-1]

        # Register waiter and wait
        waiter = asyncio.Event()
        self._waiters[event_type] = waiter
        try:
            await asyncio.wait_for(waiter.wait(), timeout=timeout)
        finally:
            self._waiters.pop(event_type, None)

        return [e for e in self.events if e.event_type == event_type][-1]

    def of_type(self, event_type: str) -> list[CaptureEvent]:
        """Return all captured events of a given type."""
        return [e for e in self.events if e.event_type == event_type]

    def count(self, event_type: str) -> int:
        """Return count of captured events of a given type."""
        return len(self.of_type(event_type))
```

**Important subtlety:** The `wait_for` method must register the waiter BEFORE the triggering event is published. In test code, this means:
```python
# WRONG: race condition
bus.publish(event)
await collector.wait_for("scoring_complete")  # waiter registered AFTER publish

# RIGHT: but only needed when event_type isn't already captured
# Most patterns work naturally because:
# 1. Test publishes triggering event
# 2. EventBus.publish() calls asyncio.create_task() but task hasn't run yet
# 3. collector.wait_for() registers waiter
# 4. Event loop runs, task executes, subscriber fires, waiter is set
```

Actually, the pattern works naturally because `asyncio.create_task()` schedules the task but doesn't run it until the current coroutine yields. So the sequence `bus.publish(event)` -> `await collector.wait_for(...)` is safe because the task runs when `wait_for` yields on `waiter.wait()`.

### Pattern 3: Integration Test Markers

**What:** Custom pytest markers to separate unit tests from integration tests.

**When to use:** Tag tests that hit real APIs, use VCR cassettes, or exercise full pipeline wiring.

**Example:**
```python
# In pyproject.toml
[tool.pytest.ini_options]
markers = [
    "integration: tests requiring full pipeline wiring or external dependencies",
    "slow: tests taking >5s (real API calls, cassette recording)",
]

# In test files
@pytest.mark.integration
@pytest.mark.vcr
async def test_scoring_engine_with_real_gemini():
    ...
```

**Usage:**
```bash
pytest -m integration          # Run only integration tests
pytest -m "not integration"    # Run only unit tests (fast)
pytest -n auto                 # All tests in parallel
```

### Anti-Patterns to Avoid

- **Mocking EventBus:** Never mock the EventBus itself. It is trivial (50 lines) and deterministic. Mocking it hides real routing bugs. Use real EventBus + EventCollector.
- **`asyncio.sleep()` for event assertion:** Every `asyncio.sleep(0.1)` is a flaky test waiting to happen. Use EventCollector.wait_for() instead.
- **Singleton reset inside individual test files:** The current pattern in `test_rate_limiter.py` (local autouse fixture resetting `_instance`) works but doesn't scale. A conftest.py autouse fixture catches all singletons for all tests.
- **`scope="session"` fixtures with xdist:** Session-scoped fixtures run once PER WORKER, not once globally. If a session fixture creates shared state, use `filelock` for coordination. (Not currently needed -- all project fixtures are function-scoped.)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test timeouts | `asyncio.wait_for()` around every test | pytest-timeout `timeout = 30` | Global declarative config, zero code changes |
| Parallel execution | Manual process spawning | pytest-xdist `-n auto` | Handles event loops, fixtures, reporting |
| HTTP recording | Manual fixture JSON files | VCR.py cassettes | Automatic recording, replay, filtering |
| Async event waiting | `asyncio.sleep()` polling | EventCollector.wait_for() | Deterministic, fast, no arbitrary delays |
| pytest VCR integration | Raw VCR context managers | pytest-recording `@pytest.mark.vcr` | Auto cassette naming, `--record-mode` CLI |

**Key insight:** All five tools are config/fixture additions. Zero production code changes are needed for Phase 7. The only new code is the EventCollector helper class and conftest.py fixtures.

## Common Pitfalls

### Pitfall 1: Singleton Leakage Across Tests

**What goes wrong:** `default_health.mark_unhealthy("cartesia_tts")` in `test_qa.py` line 526 persists into subsequent tests. If tests run in a different order (xdist), previously-passing tests fail because `default_health.is_healthy("cartesia_tts")` returns False unexpectedly.

**Why it happens:** Module-level singletons (`default_bus`, `default_health`, `GeminiRateLimiter._instance`) persist for the lifetime of the Python process. Tests that mutate them without cleanup pollute the global state.

**How to avoid:** Autouse conftest.py fixture that replaces module-level singleton references before each test.

**Warning signs:** Tests pass in isolation (`pytest tests/test_qa.py::TestPipelineDelivery`) but fail when run after other tests. Tests fail with xdist but pass sequentially.

### Pitfall 2: asyncio.sleep(0) Is Not Always Enough

**What goes wrong:** `await asyncio.sleep(0)` yields to the event loop once, but if the subscriber callback itself schedules more tasks (e.g., `_reveal_score` which does multiple awaits), a single yield is insufficient.

**Why it happens:** `asyncio.sleep(0)` only runs ready tasks once. Multi-step async chains require multiple yields.

**How to avoid:** EventCollector.wait_for() polls until the expected event appears, naturally handling multi-step chains.

**Warning signs:** Tests with `await asyncio.sleep(0)` pass locally but fail in CI or under load.

### Pitfall 3: pytest-asyncio auto Mode Removes Marker Requirement

**What goes wrong:** Setting `asyncio_mode = "auto"` in pyproject.toml means ALL async test functions and fixtures are automatically treated as asyncio tests. If a test file accidentally defines an `async def test_*` that was NOT meant to be an asyncio test, it will be silently collected.

**Why it happens:** Auto mode is designed for projects that are purely asyncio (which arbiter is). The 170 existing `@pytest.mark.asyncio` markers become redundant but harmless.

**How to avoid:** Use auto mode (it's the right choice for this project). The existing markers don't need removal -- they're no-ops in auto mode. All tests in the project are already correctly marked.

**Warning signs:** None in practice. Auto mode simplifies configuration.

### Pitfall 4: VCR.py Cassette Drift with google-genai SDK

**What goes wrong:** VCR.py records cassettes against a specific google-genai SDK version. When the SDK updates, request payloads may change (new headers, different URL paths), causing cassette mismatches.

**Why it happens:** google-genai uses custom httpx clients (`SyncHttpxClient`, `AsyncHttpxClient` subclassing `httpx.Client`/`httpx.AsyncClient`). VCR.py 8.x patches httpcore underneath, which should be transport-agnostic. But SDK updates can change the HTTP requests themselves.

**How to avoid:**
1. Use `filter_headers` to strip volatile headers (api keys, user-agent, x-goog-api-key)
2. Set `record_mode = "none"` in CI (replay only)
3. Use `--record-mode=once` locally to refresh cassettes
4. Keep cassettes in git so CI always has recordings to replay

**Warning signs:** Tests pass locally (where real API is available) but fail in CI (where cassettes are stale).

### Pitfall 5: pytest-xdist Worker Isolation with Shared Temp Dirs

**What goes wrong:** Tests using `tmp_path` get worker-specific temp dirs automatically (pytest-xdist handles this). But if tests read/write to hardcoded paths (like `data/scores/`), workers collide.

**Why it happens:** The `ScoringPipeline` and `DeliberationPipeline` constructors accept `scores_dir` and `observations_dir` parameters with defaults like `"data/scores"`. Tests that don't override these defaults share the same filesystem paths.

**How to avoid:** Existing test fixtures already use `tmp_path` for data directories (see `test_deliberation_pipeline.py` line 87-94). Verify all pipeline tests follow this pattern.

**Warning signs:** Intermittent failures with xdist: file-not-found or unexpected data from another worker's test.

### Pitfall 6: pytest-timeout method="signal" Does Not Work in Threads

**What goes wrong:** The default timeout method is `"signal"`, which uses `SIGALRM`. This only works in the main thread. pytest-xdist runs tests in worker processes (not threads), so signal method works. But if any test spawns threads internally, signal-based timeout cannot interrupt them.

**Why it happens:** POSIX signals can only be delivered to the main thread.

**How to avoid:** Use `timeout_method = "thread"` in pyproject.toml for maximum compatibility. Thread method works everywhere but cannot interrupt blocking I/O (which is fine for async tests that use `await`).

**Warning signs:** Timeout not triggering for tests that block inside threads.

## Code Examples

Verified patterns from official sources:

### pyproject.toml Configuration (Complete)

```toml
# Source: pytest-timeout docs, pytest-xdist docs, pytest-asyncio docs
[tool.pytest.ini_options]
asyncio_mode = "auto"
timeout = 30
timeout_method = "thread"
addopts = "-x --tb=short"
markers = [
    "integration: tests requiring full pipeline wiring or external dependencies",
    "slow: tests taking >5s (real API calls, cassette recording)",
]
```

### conftest.py Singleton Reset + EventCollector Fixture

```python
# tests/conftest.py
# Source: Pattern from existing test_rate_limiter.py line 25-27, generalized
import pytest

import src.capture.event_bus as event_bus_module
import src.resilience.health as health_module
from src.capture.event_bus import EventBus
from src.resilience.health import ServiceHealth
from src.resilience.rate_limiter import GeminiRateLimiter
from tests.helpers.event_collector import EventCollector


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset module-level singletons between every test."""
    event_bus_module.default_bus = EventBus()
    health_module.default_health = ServiceHealth()
    GeminiRateLimiter._instance = None
    yield
    event_bus_module.default_bus = EventBus()
    health_module.default_health = ServiceHealth()
    GeminiRateLimiter._instance = None


@pytest.fixture
def event_collector(event_bus: EventBus) -> EventCollector:
    """Create an EventCollector bound to the given event_bus fixture."""
    return EventCollector(event_bus)
```

### VCR Configuration Fixture

```python
# tests/conftest.py (continued)
# Source: VCR.py docs - filter_headers, pytest-recording docs
@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [
            "authorization",
            "x-api-key",
            "x-goog-api-key",
            "anthropic-api-key",
        ],
        "record_mode": "none",  # CI: replay only. Use --record-mode=once locally.
        "cassette_library_dir": "tests/cassettes",
        "decode_compressed_response": True,
    }
```

### EventCollector Usage in Tests

```python
# Replace asyncio.sleep(0) pattern
# BEFORE (current pattern in test_scoring_pipeline.py line 155):
event = ObservationVerified(output=sanitized)
await pipeline._on_observation_verified(event)
await asyncio.sleep(0)
assert len(received) == 1

# AFTER (with EventCollector):
event = ObservationVerified(output=sanitized)
await pipeline._on_observation_verified(event)
scoring_event = await collector.wait_for("scoring_complete", timeout=5.0)
assert scoring_event.scorecard.team_name == "TestTeam"
```

### Integration Test Marker Usage

```python
# Source: pytest docs - custom markers
@pytest.mark.integration
@pytest.mark.vcr
async def test_gemini_scoring_engine_real_response():
    """Integration test: score a demo using real Gemini API (cassette replay)."""
    engine = ScoringEngine(api_key="test-key")
    scorecard = await engine.score(sanitized, "ROGUE::AGENT")
    assert scorecard.total_score > 0
```

### pytest-xdist Parallel Run

```bash
# Source: pytest-xdist docs
pytest -n auto                    # Auto-detect CPU cores
pytest -n auto -m "not slow"     # Skip slow tests in parallel
pytest -n 0                       # Disable parallel (debugging)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| VCR.py patches httpx directly | VCR.py 8.x patches httpcore | VCR.py 8.0.0 (2025) | Fixes httpx.ResponseNotRead exceptions, supports custom httpx transports |
| pytest-asyncio strict mode (marker required) | auto mode (all async tests auto-detected) | pytest-asyncio 1.0 | Eliminates need for `@pytest.mark.asyncio` on every test |
| `asyncio.sleep()` for event assertion | EventCollector with async wait_for | Pattern established | Deterministic, no arbitrary delays, faster tests |

**Deprecated/outdated:**
- `google-generativeai` SDK (old): Deprecated in favor of `google-genai` (the unified SDK this project uses)
- VCR.py <6.0: Had broken binary format in cassettes; recreate cassettes if upgrading from <6.0

## Open Questions

1. **VCR.py + google-genai WebSocket (Live API)**
   - What we know: VCR.py records HTTP interactions. google-genai's `aio.live.connect()` uses WebSocket, not REST HTTP.
   - What's unclear: VCR.py likely cannot record WebSocket streams. The Live API (used by `GeminiSession`) is not a standard HTTP request.
   - Recommendation: Use VCR.py ONLY for REST API calls (`aio.models.generate_content` used by ScoringEngine, GeminiProvider, QAGenerator, CommentaryGenerator). For Live API tests, use the existing `RehearsalGeminiSession` mock pattern. This is not a blocker -- Live API testing is Phase 8 (E2E) scope, not Phase 7.

2. **pytest-recording with VCR.py 8.1.1**
   - What we know: pytest-recording 0.13.4 wraps VCR.py. VCR.py is at 8.1.1.
   - What's unclear: No explicit version pinning or compatibility matrix between pytest-recording and VCR.py 8.x was found in docs.
   - Recommendation: Install both and run a quick validation test. If pytest-recording breaks with VCR.py 8.x, fall back to using VCR.py directly via context managers (minor inconvenience, not a blocker). **Confidence: MEDIUM** -- likely works since VCR.py maintains backward-compatible API.

3. **Existing `asyncio.sleep()` calls in test_tui.py (80+ occurrences)**
   - What we know: `test_tui.py` uses Textual's headless test mode. The `SLEEP = 0.15` constant is needed for Textual widget rendering, not EventBus timing.
   - What's unclear: Whether EventCollector can replace these sleeps, or if they are intrinsic to Textual's async rendering pipeline.
   - Recommendation: Do NOT attempt to replace `asyncio.sleep()` calls in `test_tui.py` during Phase 7. Those sleeps are for Textual widget rendering sync, not EventBus timing. Focus EventCollector usage on pipeline tests (`test_scoring_pipeline.py`, `test_deliberation_pipeline.py`, future E2E tests).

4. **pytest-asyncio `asyncio_default_fixture_loop_scope` setting**
   - What we know: pytest-asyncio 1.3.0+ supports `asyncio_default_fixture_loop_scope` configuration. Current project has no explicit setting.
   - What's unclear: Whether the default (function scope) is correct for all fixtures, or if some should be session-scoped.
   - Recommendation: Explicitly set `asyncio_default_fixture_loop_scope = "function"` in pyproject.toml to match the default and avoid future deprecation warnings. All existing fixtures are function-scoped, so this changes nothing.

## Sources

### Primary (HIGH confidence)
- pytest-timeout Context7 (`/pytest-dev/pytest-timeout`) -- configuration, decorator syntax, method options
- pytest-xdist Context7 (`/pytest-dev/pytest-xdist`) -- worker isolation, worker_id fixture, configuration
- VCR.py Context7 (`/kevin1024/vcrpy`) -- filter_headers, record_mode, custom_patches, httpx support
- [VCR.py Changelog](https://vcrpy.readthedocs.io/en/latest/changelog.html) -- v8.0.0 httpcore rewrite confirmed
- [pytest-asyncio Configuration](https://pytest-asyncio.readthedocs.io/en/latest/reference/configuration.html) -- auto mode, fixture loop scope
- [google-genai source: `_api_client.py`](https://github.com/googleapis/python-genai/blob/v1.53.0/google/genai/_api_client.py) -- confirmed httpx as default transport, aiohttp optional
- Direct codebase analysis: `src/capture/event_bus.py`, `src/resilience/health.py`, `src/resilience/rate_limiter.py`, all 13 test files

### Secondary (MEDIUM confidence)
- [VCR.py PyPI](https://pypi.org/project/vcrpy/) -- version 8.1.1, Python 3.10-3.13 support
- [pytest-recording PyPI](https://pypi.org/project/pytest-recording/) -- version 0.13.4, Python 3.9-3.13 support
- [pytest-timeout PyPI](https://pypi.org/project/pytest-timeout/) -- version 2.4.0, May 2025
- [pytest-xdist PyPI](https://pypi.org/project/pytest-xdist/) -- version 3.8.0, July 2025

### Tertiary (LOW confidence)
- VCR.py + google-genai compatibility: No direct documentation or community reports found. Inferred from google-genai using httpx and VCR.py 8.x supporting httpx via httpcore patching. Needs empirical validation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries are stable, well-maintained, version-verified on PyPI, and support Python 3.13
- Architecture patterns: HIGH -- Singleton reset pattern already proven locally in test_rate_limiter.py; EventCollector follows established async pub/sub testing pattern
- Pitfalls: HIGH -- Identified from direct codebase analysis (counted singleton references, sleep calls, module-level state)
- VCR.py + google-genai: MEDIUM -- Transport compatibility verified (both use httpx), but no community reports of this specific combination. WebSocket Live API is definitively NOT recordable.

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (stable libraries, 30-day window)
