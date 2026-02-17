# Technology Stack: v1.1 Additions

**Project:** Arbiter v1.1 -- Reliability, E2E Testing, Rehearsal Mode, MoE Hardening, Dashboard Polish
**Researched:** 2026-02-17
**Scope:** NEW additions only. Existing validated stack (Python 3.13, Gemini, Cartesia, FastAPI, React/Vite/Zustand, pytest/pytest-asyncio) is NOT re-researched.

---

## Summary of Changes

The existing stack is sound. v1.1 adds **4 Python dev dependencies**, **1 npm devDependency**, and **zero production dependencies**. Everything new is test/dev tooling. The reliability and rehearsal features are architectural patterns built on existing abstractions (EventBus, LLMProvider, CaptureConfig), not library additions.

---

## Recommended Stack Additions

### 1. Python: Test Infrastructure Hardening

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pytest-timeout** | >=2.4.0 | Kill hanging async tests | E2E tests span the full pipeline (capture -> defense -> commentary -> scoring -> deliberation). A stuck mock or deadlocked event bus callback hangs the entire CI run. pytest-timeout aborts individual tests after a configurable deadline. Compatible with pytest >=9 and pytest-asyncio 1.3.0. No code changes -- add `--timeout=30` to pytest invocation or `timeout = 30` in pyproject.toml. |
| **pytest-xdist** | >=3.5 | Parallel test execution | 371 tests growing to 500+ with E2E additions. Sequential runs will exceed 60s. pytest-xdist distributes across cores (`-n auto`). Each worker gets its own event loop, so no shared state issues. The existing `EventBus()` instantiation pattern (fresh instance per test via fixtures) is already xdist-safe. |

**Confidence:** HIGH -- Both are stable, well-maintained pytest plugins. pytest-timeout 2.4.0 released May 2025. pytest-xdist 3.5+ confirmed compatible with pytest 9 and pytest-asyncio 1.3.0 via official docs.

**Why NOT `pytest-parallel`:** Abandoned since 2020, no pytest-asyncio support.
**Why NOT `anyio`/`trio` test harness:** The project is pure asyncio. Adding a second async runtime creates confusion.

### 2. Python: API Response Recording (for MoE E2E tests)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pytest-recording** | >=0.13.2 | VCR.py integration for pytest | Records real HTTP responses to YAML cassettes for deterministic replay. Prevents flaky tests from Groq/OpenAI/Anthropic rate limits in CI. Use `@pytest.mark.vcr` decorator on integration tests that hit real APIs. Not needed for unit tests (use `AsyncMock` there). |
| **vcrpy** | >=6.0 | HTTP interaction recording engine | Underlying cassette engine. Records all HTTP traffic for a test run to YAML, replays on subsequent runs. Works with `openai` and `anthropic` SDKs because they use httpx/httpcore internally. |

**Confidence:** MEDIUM -- VCR.py works with httpx-based SDKs (openai >=1.50 and anthropic >=0.40 both use httpx internally). The `google-genai` SDK uses its own gRPC/REST transport which may need `filter_headers` tuning. If google-genai cassettes prove unreliable, fall back to `AsyncMock` for Gemini-specific tests.

**Why NOT `respx`:** Mocks httpx transport directly. Would require understanding each SDK's internal HTTP layer. More coupling than VCR.py's network-level recording.
**Why NOT `pytest-httpx`:** Same issue -- too tightly coupled to httpx internals.

### 3. Dashboard: WebSocket Test Mocking

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **vitest-websocket-mock** | ^0.5.0 | Mock WebSocket server for Vitest | The operator dashboard communicates entirely via WebSocket (`/ws/operator`). Current store tests (`operatorStore.test.ts`) test dispatch logic but never test actual WebSocket connection, reconnection, or error handling. vitest-websocket-mock creates a mock WS server in-process, validates messages sent by the client, and simulates disconnects/errors. Auto-detects `@testing-library/react` and wraps updates in `act()`. |

**Confidence:** HIGH -- v0.5.0 is the standard for WebSocket testing in Vitest. Compatible with jsdom environment already configured in `vitest.config.ts`. No build config changes needed.

**Why NOT MSW WebSocket:** Requires Node.js 22+ `WebSocket` global. jsdom does not provide a native WebSocket implementation, making MSW WebSocket mocking fragile in Vitest's jsdom environment.
**Why NOT `ws` library directly:** Would need manual mock server setup. vitest-websocket-mock provides custom matchers (`.toReceiveMessage()`, `.toHaveReceivedMessages()`) and auto-act() integration.

### 4. Dashboard: Browser E2E (OPTIONAL, stretch goal)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **@playwright/test** | ^1.58.0 | Browser E2E tests for operator dashboard | Full browser testing against a real FastAPI backend. Playwright handles WebSocket inspection natively (`page.waitForEvent('websocket')`), supports Chrome/Firefox/Safari, runs headless in CI. OPTIONAL for v1.1 -- Python-side E2E is the priority. |

**Confidence:** HIGH for Playwright as the right tool. LOW priority for v1.1 scope.

**Why NOT Cypress:** Playwright has native WebSocket inspection. Cypress requires plugins for WebSocket testing and is slower for WebSocket-heavy apps.

---

## What Does NOT Need New Libraries

### Rehearsal/Dry-Run Mode

**Zero new dependencies.** Rehearsal mode is an architectural pattern built on existing abstractions.

The project already has the right primitives:
- `EventBus` with pub/sub decoupling -- synthetic events can be injected without camera/audio hardware
- `DemoMachine` state machine accepts `start_demo`/`stop_demo` programmatically
- `CaptureConfig` (Pydantic) can be extended with `rehearsal_mode: bool` and `rehearsal_fixture_path: str`
- `LLMProvider` base class returns `str` from `generate()` -- a `ReplayProvider` subclass that reads canned responses from fixture files fits cleanly
- `CapturePipeline.__init__()` already conditionally wires components based on config (see line 94-108 for MoE conditional wiring)

What to BUILD (not install):
1. **`ReplayProvider(LLMProvider)`** -- reads canned LLM responses from JSON fixture files, returns them in sequence
2. **`SyntheticCapture`** -- publishes pre-recorded `KeyFrameDetected` / `TranscriptReceived` events from fixture data at realistic timing intervals
3. **`rehearsal_mode` config flag** -- when True, swaps Camera/Audio/GeminiSession for SyntheticCapture in `CapturePipeline.__init__`
4. **Fixture files** in `data/rehearsals/` -- JSON files containing event sequences, LLM responses, and timing data from real captured demos

### Groq Scoring Fallback

**Zero new dependencies.** Groq access via the OpenAI-compatible API is already established in `CommentaryGenerator._call_groq()` using the installed `openai` SDK.

What to BUILD:
1. **`GroqScoringProvider(LLMProvider)`** -- wraps `AsyncOpenAI(base_url="https://api.groq.com/openai/v1")` with `model="llama-3.3-70b-versatile"` and `response_format={"type": "json_object"}`
2. **Factory registration** -- add `elif name_lower == "groq": return GroqScoringProvider(api_key=api_key)` to `providers/factory.py`
3. **Pipeline wiring** -- add Groq to `MoEScoringEngine` provider list when `groq_api_key` is configured

**Critical detail on Groq JSON mode:**
- Llama 3.3 70B Versatile supports `json_object` mode (best-effort JSON), NOT `json_schema` strict mode (which is limited to GPT-OSS models on Groq per their structured outputs docs)
- The scoring parser (`ScoringEngine._parse_and_validate()`) already handles raw JSON text with try/except fallback
- If Groq produces malformed JSON, the MoE aggregator drops that provider's contribution (existing behavior in `moe_engine.py` lines 72-93 for failed providers)
- Groq Llama 3.3 70B runs at ~280 tokens/sec with 128K context / 32K output -- well within scoring prompt needs

### MoE Multi-Provider E2E Testing

**No new test libraries beyond pytest-recording/vcrpy (above).** The MoE pipeline already has unit tests in `test_moe_demos.py`. E2E tests need:
- `unittest.mock.AsyncMock` (stdlib) for mock providers returning canned scoring JSON
- pytest-recording for optional real-API smoke tests
- The `EventBus` + fixtures pattern already established in `test_scoring_pipeline.py`

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Test parallelism | pytest-xdist | pytest-parallel | Abandoned 2020, no asyncio support |
| Test timeouts | pytest-timeout | manual `asyncio.wait_for()` wrappers | Boilerplate in every test; pytest-timeout is declarative |
| Async mocking | unittest.mock.AsyncMock (stdlib) | respx | respx is httpx-specific; our SDKs abstract HTTP |
| API recording | pytest-recording + vcrpy | manual fixture files only | VCR gives deterministic replay without hand-authoring |
| WS test (dashboard) | vitest-websocket-mock | MSW WebSocket | MSW needs Node 22+ WebSocket global; jsdom lacks it |
| WS test (dashboard) | vitest-websocket-mock | ws + manual mock | vitest-websocket-mock has custom matchers, auto-act() |
| Browser E2E | Playwright | Cypress | Native WS inspection, faster headless, better DX |
| Rehearsal data | Custom JSON fixtures | VCR cassette replay | Rehearsal replays domain events (EventBus), not HTTP |
| Groq scoring | json_object mode | json_schema strict | Llama 3.3 70B does not support json_schema on Groq |

---

## What NOT to Add

| Library | Why Avoid |
|---------|-----------|
| `httpx` (direct dep) | All API access goes through SDK clients (google-genai, openai, anthropic). Adding httpx as a direct dependency creates a parallel HTTP path that diverges from production behavior. Tests should mock at the SDK level. |
| `aiohttp` | Project does not use aiohttp. The Lakera Guard integration from v1.0 research was replaced by in-process defense pipeline. |
| `pytest-mock` | `unittest.mock` from stdlib is sufficient. 170+ existing tests already use `AsyncMock` and `MagicMock`. Adding pytest-mock's `mocker` fixture would create two mocking patterns. Consistency > convenience. |
| `factory-boy` | Test fixtures are simple Pydantic models instantiated directly. Factory-boy adds ORM-oriented complexity for no gain. |
| `hypothesis` | Property-based testing is overkill. The scoring rubric has fixed criteria -- there is no combinatorial input space to explore. |
| `docker-compose` for test services | No external services (no database, no Redis, no message queue). Everything is in-process async. |
| `locust` / `k6` for load testing | Arbiter serves 1-2 operator connections and 1 audience display. Load testing a single-user system is pointless. |
| `Selenium` | Playwright supersedes it completely. Selenium WebSocket support is poor. |

---

## Installation

### Python dev dependencies (update pyproject.toml)

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.2",
    "pytest-asyncio>=1.3.0",
    "pytest-timeout>=2.4.0",
    "pytest-xdist>=3.5",
    "pytest-recording>=0.13.2",
    "vcrpy>=6.0",
]
```

```bash
uv sync --group dev
```

### Dashboard devDependencies

```bash
cd operator-dashboard
npm install -D vitest-websocket-mock@^0.5.0
```

### Optional: Playwright (stretch goal, skip for v1.1 core)

```bash
cd operator-dashboard
npm install -D @playwright/test@^1.58.0
npx playwright install --with-deps chromium
```

---

## Configuration

### pytest configuration (add to pyproject.toml)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
timeout = 30
addopts = "-x --tb=short"
markers = [
    "e2e: end-to-end integration tests spanning full pipeline",
    "rehearsal: tests using rehearsal/replay mode",
    "slow: tests that take >5s (real API calls, cassette recording)",
]
```

**Why `asyncio_mode = "auto"`:** The project has 170 tests using `@pytest.mark.asyncio`. Auto mode makes the marker optional (already-marked tests still work). Since pytest-asyncio 1.3.0 is installed (confirmed via venv check), auto mode is fully supported. No test rewrites needed -- existing markers become redundant but harmless.

**Why `timeout = 30`:** E2E tests spanning the full pipeline (EventBus -> defense -> scoring -> display) should complete in under 10s with mocked providers. 30s gives 3x headroom before a hung test is killed. Individual tests can override with `@pytest.mark.timeout(60)` if needed.

### VCR cassette configuration (new conftest.py)

```python
# tests/conftest.py
import pytest

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

---

## Integration Points

```
Existing Component         New Addition                Connection Point
---------------------------------------------------------------------------
CapturePipeline.__init__   ReplayProvider              Config flag swaps providers
CapturePipeline.__init__   SyntheticCapture            Config flag swaps camera/audio
EventBus.publish()         SyntheticCapture            Injects fixture events
MoEScoringEngine           GroqScoringProvider         Added to providers list
providers/factory.py       "groq" name mapping         New elif branch
ScoringEngine._parse_*     Groq json_object output     Already handles raw JSON
CaptureConfig              rehearsal_mode field         New Pydantic field
CaptureConfig              groq_scoring_enabled        New Pydantic field
WebOperator + FastAPI WS   vitest-websocket-mock       Tests mock WS server
test_scoring_pipeline.py   pytest-timeout              Global timeout guard
test_moe_demos.py          pytest-recording/vcrpy      @pytest.mark.vcr on API tests
All 371+ tests             pytest-xdist                -n auto parallelism
```

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| pytest-timeout / pytest-xdist | HIGH | Stable, verified versions, compatible with existing test stack |
| vitest-websocket-mock | HIGH | Standard Vitest WS testing library, compatible with existing jsdom setup |
| Groq scoring via OpenAI SDK | HIGH | Pattern already proven in commentary fallback (`generator.py`) |
| Groq json_object mode | HIGH | Verified via Groq structured outputs docs |
| Groq json_schema strict mode NOT available | HIGH | Groq docs confirm strict mode limited to GPT-OSS models |
| pytest-recording / vcrpy | MEDIUM | Works with httpx-based SDKs; google-genai may need tuning |
| Rehearsal mode (no new deps) | HIGH | Pure architectural pattern using existing EventBus/LLMProvider abstractions |
| Playwright E2E | HIGH (tool choice), LOW (priority) | Right tool but stretch goal for v1.1 |

---

## Sources

- [pytest-timeout PyPI](https://pypi.org/project/pytest-timeout/) -- version 2.4.0, released May 2025
- [pytest-xdist docs](https://pytest-xdist.readthedocs.io/) -- parallel test distribution
- [pytest-xdist PyPI](https://pypi.org/project/pytest-xdist/) -- version 3.5+
- [pytest-asyncio docs](https://pytest-asyncio.readthedocs.io/en/latest/concepts.html) -- auto mode configuration
- [pytest-asyncio changelog](https://pytest-asyncio.readthedocs.io/en/v0.25.2/reference/changelog.html) -- v1.3.0 release notes
- [Groq Structured Outputs docs](https://console.groq.com/docs/structured-outputs) -- json_schema limited to GPT-OSS models; json_object available for Llama models
- [Groq Llama 3.3 70B Versatile](https://console.groq.com/docs/model/llama-3.3-70b-versatile) -- 128K context, 32K output, ~280 tok/s, json_object mode
- [vitest-websocket-mock npm](https://www.npmjs.com/package/vitest-websocket-mock) -- v0.5.0
- [vitest-websocket-mock GitHub](https://github.com/akiomik/vitest-websocket-mock) -- API docs, auto-act() integration
- [Playwright Python releases](https://playwright.dev/python/docs/release-notes) -- v1.58.0, released Jan 2026
- [pytest-recording PyPI](https://pypi.org/project/pytest-recording/) -- VCR.py pytest integration
- [VCR.py docs](https://vcrpy.readthedocs.io/) -- v6.0+ with httpx support
- [FastAPI async test docs](https://fastapi.tiangolo.com/advanced/async-tests/) -- httpx AsyncClient patterns
