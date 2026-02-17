# Phase 9: Groq Fallback + Rehearsal Mode - Research

**Researched:** 2026-02-17
**Domain:** LLM provider fallback, async timeout patterns, synthetic capture/replay
**Confidence:** HIGH

## Summary

Phase 9 combines two conceptually distinct but practically complementary features: (1) adding Groq as a scoring fallback provider with MoE timeout hardening, and (2) building a rehearsal mode that runs the full pipeline with synthetic data and no real hardware or API calls.

The Groq scoring provider is straightforward to implement because the codebase already has an established `LLMProvider` interface with three existing implementations (Gemini, Claude, OpenAI), and Groq is already used in the commentary layer via the OpenAI-compatible SDK. The key architectural work is: implementing `GroqProvider` as an `LLMProvider`, adding it to the factory, adding Groq calibration to `ScoreAggregator`, and replacing `asyncio.gather` in `MoEScoringEngine` with `asyncio.wait` + hard timeout.

Rehearsal mode requires three new components: a synthetic capture feed (mock camera + audio events injected into EventBus), a replay LLM provider (returns canned JSON responses), and CLI/dashboard integration (`--rehearsal` flag + dashboard command). The existing E2E test patterns (from Phase 8) already demonstrate the full mock pipeline setup, making this a straightforward extraction into a runtime-accessible rehearsal feature.

**Primary recommendation:** Build GroqProvider following the exact OpenAIProvider pattern (it uses the same SDK), add timeout-bounded `asyncio.wait` to MoEScoringEngine, then build rehearsal mode by extracting the E2E test's `_setup_full_pipeline` pattern into a production `RehearsalPipeline`.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `openai` | >=1.50 (already in deps) | Groq API client via OpenAI-compatible endpoint | Groq uses OpenAI-compatible API; already used in CommentaryGenerator and QAGenerator for Groq fallback |
| `asyncio` (stdlib) | N/A | `asyncio.wait` with `FIRST_COMPLETED` + hard timeout for MoE | Stdlib, no new dependency; replaces `asyncio.gather` for timeout-bounded concurrency |
| `pydantic` | ~2.11 (already in deps) | Config models for rehearsal mode | Already used throughout for all data models |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tenacity` | ~9.0 (already in deps) | Retry decorator for GroqProvider | Same pattern as OpenAIProvider and ClaudeProvider |
| `argparse` (stdlib) | N/A | `--rehearsal` CLI flag | Already used in `src/main.py` for `--operator` and `--cli` flags |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| OpenAI SDK for Groq | `groq` native SDK (`AsyncGroq`) | Native Groq SDK exists (v1.x) but OpenAI-compatible SDK is already in deps and already proven for Groq in commentary/QA generators. Adding `groq` would add a dependency for zero benefit. |
| `asyncio.wait` for MoE timeout | `asyncio.wait_for` wrapping `asyncio.gather` | `wait_for` cancels the entire gather on timeout, losing partial results. `asyncio.wait` with `timeout` returns both done and pending sets, allowing partial result aggregation. |
| Manual timeout tracking | `anyio.move_on_after` | Adds a dependency. `asyncio.wait` is stdlib and does exactly what we need. |

**Installation:** No new dependencies needed. All libraries already in `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
```
src/
├── providers/
│   ├── base.py               # LLMProvider ABC (unchanged)
│   ├── groq_provider.py      # NEW: GroqProvider implementing LLMProvider
│   ├── factory.py            # Updated: add "groq" case
│   └── __init__.py           # Updated: export GroqProvider
├── scoring/
│   ├── moe_engine.py         # Updated: asyncio.wait with timeout
│   └── aggregator.py         # Updated: add "groq" calibration
├── rehearsal/                 # NEW: rehearsal mode module
│   ├── __init__.py
│   ├── synthetic_capture.py   # Mock camera + audio events
│   ├── replay_provider.py     # Canned LLM responses
│   └── rehearsal_pipeline.py  # Full rehearsal orchestrator
└── main.py                    # Updated: --rehearsal flag
```

### Pattern 1: GroqProvider (following OpenAIProvider pattern exactly)
**What:** A new `LLMProvider` implementation for Groq using the OpenAI-compatible SDK at `https://api.groq.com/openai/v1`
**When to use:** Scoring fallback when Gemini is unavailable
**Example:**
```python
# Source: existing pattern from src/providers/openai_provider.py + src/commentary/generator.py
from openai import AsyncOpenAI, APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter, before_sleep_log
from src.providers.base import LLMProvider

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

GROQ_RETRY = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=10, jitter=2),
    retry=retry_if_exception_type((
        ConnectionError, TimeoutError, OSError,
        APIConnectionError, APITimeoutError, InternalServerError, RateLimitError,
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile") -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=_GROQ_BASE_URL, timeout=20.0)
        self._model = model

    @property
    def name(self) -> str:
        return f"groq:{self._model}"

    async def generate(self, prompt: str, system_prompt: str, *, temperature: float = 0.3, max_tokens: int = 1000) -> str:
        try:
            return await self._call_groq(prompt, system_prompt, temperature, max_tokens)
        except Exception:
            logger.exception("Groq generation failed for model %s", self._model)
            return ""

    @GROQ_RETRY
    async def _call_groq(self, prompt: str, system_prompt: str, temperature: float, max_tokens: int) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},  # Enforce JSON output for scoring
        )
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content or ""
        return ""
```

### Pattern 2: MoE Timeout with asyncio.wait (REL-02)
**What:** Replace unbounded `asyncio.gather` with `asyncio.wait` + hard timeout, allowing partial results from fast providers while cancelling slow ones.
**When to use:** MoEScoringEngine.score() to ensure 15-second hard cap.
**Example:**
```python
# Source: Python stdlib asyncio docs — asyncio.wait with timeout
MOE_TIMEOUT = 15.0  # seconds — hard cap per success criterion

async def score(self, sanitized, track, criteria=None, track_criteria=None):
    # ... build prompt ...

    # Create named tasks for each provider
    tasks = {
        asyncio.create_task(
            provider.generate(prompt=prompt, system_prompt=SCORING_SYSTEM_PROMPT,
                              temperature=0.3, max_tokens=1500),
            name=provider.name,
        ): provider
        for provider in self._providers
    }

    # Wait with hard timeout — returns (done, pending)
    done, pending = await asyncio.wait(
        tasks.keys(),
        timeout=MOE_TIMEOUT,
        return_when=asyncio.ALL_COMPLETED,
    )

    # Cancel any providers that didn't finish
    for task in pending:
        task.cancel()
        provider = tasks[task]
        logger.warning("Provider %s timed out after %.0fs, cancelling", provider.name, MOE_TIMEOUT)

    # Collect results from completed tasks
    # ... parse done tasks, aggregate as before ...
```

### Pattern 3: Synthetic Capture Feed (RHS-01)
**What:** A class that publishes mock camera/audio/demo events into EventBus without real hardware.
**When to use:** Rehearsal mode — simulates a complete demo lifecycle.
**Example:**
```python
# Source: existing patterns from test_e2e_pipeline_chain.py and CapturePipeline
class SyntheticCapture:
    """Publishes synthetic demo events into an EventBus for rehearsal mode."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    async def run_demo(self, team_name: str, track: str, duration: float = 180.0) -> None:
        """Simulate a full demo lifecycle with synthetic events."""
        self._event_bus.publish(DemoStarted(team_name=team_name))
        await asyncio.sleep(0.5)  # Brief pause for theatrical effect

        # Publish synthetic key frames and transcripts
        for i in range(3):
            self._event_bus.publish(KeyFrameDetected(frame=_make_synthetic_frame()))
            await asyncio.sleep(0.3)

        for segment in _SYNTHETIC_TRANSCRIPTS:
            self._event_bus.publish(TranscriptReceived(segment=segment))
            await asyncio.sleep(0.2)

        self._event_bus.publish(DemoStopped(team_name=team_name, duration=duration))
```

### Pattern 4: Replay Provider (RHS-02)
**What:** An `LLMProvider` implementation that returns canned JSON responses instead of calling real APIs.
**When to use:** Rehearsal mode — deterministic, no API keys needed.
**Example:**
```python
class ReplayProvider(LLMProvider):
    """Returns canned LLM responses for deterministic rehearsal runs."""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self._responses = responses or _DEFAULT_REPLAY_RESPONSES
        self._call_count = 0

    @property
    def name(self) -> str:
        return "replay"

    async def generate(self, prompt: str, system_prompt: str, **kwargs) -> str:
        self._call_count += 1
        # Return canned scoring response if scoring system prompt detected
        if "scoring engine" in system_prompt.lower():
            return self._responses.get("scoring", _DEFAULT_SCORING_RESPONSE)
        # Return canned commentary if persona prompt detected
        if "arbiter" in system_prompt.lower():
            return self._responses.get("commentary", _DEFAULT_COMMENTARY_RESPONSE)
        return self._responses.get("default", "")
```

### Anti-Patterns to Avoid
- **Sharing OpenAI client instances:** Each GroqProvider must create its own `AsyncOpenAI` client. Do not share with commentary/QA Groq clients.
- **Using `asyncio.gather` with timeout via `wait_for`:** This cancels ALL tasks on timeout, losing results from providers that already finished. Use `asyncio.wait` which returns (done, pending) sets.
- **Coupling rehearsal to real config:** RehearsalPipeline must NOT load from `.env` or require any API keys. Use `CaptureConfig` with hardcoded rehearsal defaults.
- **Mixing rehearsal state with production state:** Rehearsal should write to a temp directory or skip persistence entirely (no `data/scores/` writes in rehearsal).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Groq HTTP client | Custom aiohttp wrapper | `AsyncOpenAI(base_url=_GROQ_BASE_URL)` | Already proven in commentary/QA generators. OpenAI SDK handles auth, retries, JSON parsing. |
| JSON mode enforcement | Custom prompt + regex extraction | `response_format={"type": "json_object"}` | Groq supports OpenAI-compatible `json_object` mode, guaranteeing valid JSON output without post-processing. |
| Timeout-bounded concurrency | Manual `asyncio.create_task` + timer | `asyncio.wait(tasks, timeout=N)` | Stdlib function returns (done, pending) cleanly, handles cancellation edge cases. |
| Retry with backoff | Manual sleep loop | `tenacity` retry decorator | Already used for all other providers. Consistent pattern. |

**Key insight:** The Groq provider is almost entirely copy-paste from `OpenAIProvider` with a different `base_url` and `model`. The real complexity is in the MoE timeout pattern and rehearsal orchestration, not in Groq itself.

## Common Pitfalls

### Pitfall 1: Groq JSON Mode Requires System Prompt Mention
**What goes wrong:** Groq's `response_format={"type": "json_object"}` requires the system prompt or user prompt to mention "JSON" — otherwise the API returns an error.
**Why it happens:** OpenAI-compatible JSON mode enforcement requires the prompt to contain the word "JSON" as a safety check.
**How to avoid:** The existing `SCORING_SYSTEM_PROMPT` already says "You output ONLY a JSON object" — this naturally satisfies the requirement. Verify in tests.
**Warning signs:** `BadRequestError` with message about JSON mode requiring mention of JSON in prompt.

### Pitfall 2: asyncio.wait Task Cancellation Races
**What goes wrong:** After `asyncio.wait` returns pending tasks, calling `task.cancel()` does not immediately stop the coroutine. The task continues until the next `await` point, and the cancellation may raise `CancelledError` in cleanup code.
**Why it happens:** Python's cooperative cancellation model means cancellation is not instantaneous.
**How to avoid:** After cancelling pending tasks, await them in a try/except CancelledError block to ensure proper cleanup:
```python
for task in pending:
    task.cancel()
for task in pending:
    try:
        await task
    except asyncio.CancelledError:
        pass
```
**Warning signs:** `CancelledError` propagating to callers, or pending HTTP connections not being closed.

### Pitfall 3: Groq Calibration Values Are Empirical
**What goes wrong:** Using incorrect calibration temperature/bias for Groq in `ScoreAggregator` causes score distortion when Groq is mixed with Gemini/Claude/OpenAI scores.
**Why it happens:** Each model has different scoring tendencies. Groq (Llama 3.3 70B) may score differently than GPT-4o or Gemini.
**How to avoid:** Start with neutral calibration `{"temperature": 1.0, "bias": 0.0}` and mark as needing empirical tuning. Add a note in the calibration dict. The roadmap already flags this: "Groq JSON format reliability unknown until empirical testing (Phase 9)."
**Warning signs:** Groq scores consistently higher/lower than other providers on the same demos.

### Pitfall 4: Rehearsal Mode Accidentally Requiring API Keys
**What goes wrong:** Rehearsal mode fails because `load_config()` requires `GEMINI_API_KEY` to be set.
**Why it happens:** `CaptureConfig` has `gemini_api_key: str` as a required field; `load_config()` raises `ValueError` if not present.
**How to avoid:** Create a `load_rehearsal_config()` that returns a `CaptureConfig` with placeholder API keys. Or bypass `load_config()` entirely in rehearsal mode by constructing the config directly.
**Warning signs:** `ValueError: GEMINI_API_KEY environment variable is required` when running `--rehearsal` without `.env`.

### Pitfall 5: Rehearsal Pipeline Must Wire the Same Events as Production
**What goes wrong:** Rehearsal mode skips a pipeline (e.g., deliberation) and the theatrical flow doesn't match production.
**Why it happens:** Rehearsal pipeline manually wires components instead of using the same event bus subscriptions.
**How to avoid:** Reuse the same event bus subscription pattern. Wire defense, commentary, scoring, and deliberation pipelines the same way CapturePipeline.run() does, but with mock components.
**Warning signs:** Missing events in rehearsal that exist in production (e.g., no `score_revealed` after `commentary_delivered`).

### Pitfall 6: OpenAI SDK Version Compatibility for Groq
**What goes wrong:** The `response_format` parameter for JSON mode may behave differently across `openai` SDK versions.
**Why it happens:** The codebase pins `openai>=1.50`, and the `response_format={"type": "json_object"}` feature is stable across these versions.
**How to avoid:** Use the dict format `{"type": "json_object"}` which is supported in all versions >=1.0. Avoid `json_schema` strict mode (requires newer Groq model support). The simpler `json_object` mode is sufficient for scoring.
**Warning signs:** N/A — this is stable. LOW risk.

## Code Examples

Verified patterns from the codebase and official docs:

### Groq via OpenAI SDK (already proven in codebase)
```python
# Source: src/commentary/generator.py lines 107-113
groq_key = os.environ.get("GROQ_API_KEY", "") if groq_api_key is None else groq_api_key
if groq_key:
    self._groq_client: AsyncOpenAI | None = AsyncOpenAI(
        api_key=groq_key, base_url=_GROQ_BASE_URL,
        timeout=_GROQ_TIMEOUT,
    )
```

### Groq JSON Mode (from Context7 Groq docs)
```python
# Source: Context7 /groq/groq-python — JSON object mode
response = await client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": "You are a scoring engine. Output ONLY a JSON object."},
        {"role": "user", "content": prompt},
    ],
    response_format={"type": "json_object"},
    temperature=0.3,
    max_tokens=1500,
)
```

### asyncio.wait with timeout (stdlib)
```python
# Source: Python stdlib docs — asyncio.wait
import asyncio

tasks = [asyncio.create_task(coro) for coro in coroutines]
done, pending = await asyncio.wait(tasks, timeout=15.0)

for task in pending:
    task.cancel()
# Await cancelled tasks to allow cleanup
for task in pending:
    try:
        await task
    except asyncio.CancelledError:
        pass

# Process results from done tasks
for task in done:
    try:
        result = task.result()
    except Exception as e:
        logger.warning("Task failed: %s", e)
```

### Existing MoE gather pattern (to be replaced)
```python
# Source: src/scoring/moe_engine.py lines 58-68 (CURRENT — replace this)
tasks = [
    provider.generate(
        prompt=prompt, system_prompt=SCORING_SYSTEM_PROMPT,
        temperature=0.3, max_tokens=1500,
    )
    for provider in self._providers
]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

### E2E test pattern for full pipeline mock (basis for rehearsal)
```python
# Source: tests/test_e2e_pipeline_chain.py lines 97-133
async def _setup_full_pipeline(event_bus, mock_gemini, mock_display, scorecard):
    defense = DefensePipeline(api_key="test", gemini_session=mock_gemini)
    await defense.setup(event_bus)
    commentary = CommentaryPipeline(api_key="test", voice_id="test")
    commentary._tts = MagicMock()
    commentary._display = mock_display
    commentary._generator.stream_sentences = _fake_stream_sentences
    await commentary.setup(event_bus)
    scoring = ScoringPipeline(api_key="test", display=mock_display)
    scoring._engine.score = AsyncMock(return_value=scorecard)
    await scoring.setup(event_bus)
    deliberation = DeliberationPipeline(api_key="test", display=mock_display)
    await deliberation.setup(event_bus)
    return defense, commentary, scoring, deliberation
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `asyncio.gather(*tasks)` unbounded | `asyncio.wait(tasks, timeout=N)` bounded | Python 3.11+ | Prevents MoE from hanging if one provider is down. Returns partial results. |
| Groq `json_object` mode | Groq `json_schema` strict mode | 2025 | Strict mode guarantees schema compliance. BUT only on select models and newer API. Use `json_object` for wider compatibility. |
| Manual Groq HTTP calls | OpenAI-compatible SDK | Groq SDK v1.x | No separate SDK needed. `openai` package with `base_url` override works perfectly. |

**Deprecated/outdated:**
- Groq `mixtral-8x7b-32768` — still available but `llama-3.3-70b-versatile` is the recommended model for structured JSON output. The codebase already uses `llama-3.3-70b-versatile` in commentary/QA generators.

## Key Codebase Facts for Planner

### Files to Modify
1. **`src/providers/groq_provider.py`** — NEW: ~50 LOC, copy pattern from `openai_provider.py`
2. **`src/providers/factory.py`** — Add `"groq"` case (~3 lines)
3. **`src/providers/__init__.py`** — Export `GroqProvider` (~2 lines)
4. **`src/scoring/moe_engine.py`** — Replace `asyncio.gather` with `asyncio.wait` + timeout (~20 LOC change)
5. **`src/scoring/aggregator.py`** — Add `"groq"` calibration to `DEFAULT_CALIBRATION` (~1 line)
6. **`src/capture/pipeline.py`** — Add Groq to MoE provider list if `groq_api_key` is available (~5 lines)
7. **`src/capture/config.py`** — Already has `groq_api_key: str = ""` field (no change needed)
8. **`src/rehearsal/`** — NEW module: `synthetic_capture.py`, `replay_provider.py`, `rehearsal_pipeline.py`
9. **`src/main.py`** — Add `--rehearsal` flag and rehearsal mode branch
10. **`src/operator/web.py`** — Add `"rehearsal"` action to WebSocket command handler

### Existing Groq Usage (already proven)
- `src/commentary/generator.py`: Uses `AsyncOpenAI(base_url=_GROQ_BASE_URL)` with `llama-3.3-70b-versatile` for commentary fallback
- `src/commentary/qa_generator.py`: Same pattern for Q&A question fallback
- `src/capture/config.py`: Already loads `GROQ_API_KEY` from env, stores as `groq_api_key`
- `src/commentary/pipeline.py`: Passes `groq_api_key` to generators

### Existing Config
- `CaptureConfig.groq_api_key` already exists and is loaded from `GROQ_API_KEY` env var
- `CaptureConfig.moe_scoring_enabled` already controls MoE provider list construction
- The MoE provider list is built in `CapturePipeline.__init__` (lines 94-108)

### Existing Calibration
```python
# src/scoring/aggregator.py
DEFAULT_CALIBRATION = {
    "gemini": {"temperature": 1.1, "bias": -0.2},
    "claude": {"temperature": 1.2, "bias": 0.0},
    "openai": {"temperature": 1.5, "bias": 0.3},
}
```
Groq needs to be added here. The base name extraction (`provider_name.split(":")[0]`) already handles `"groq:llama-3.3-70b-versatile"` -> `"groq"`.

### Success Criteria Mapping
| Criterion | Implementation |
|-----------|---------------|
| SC-1: Groq produces valid scores through LLMProvider | GroqProvider.generate() + JSON mode + scoring prompt -> parsed by ScoringEngine._parse_and_validate() -> saved by ScoreStore |
| SC-2: MoE completes in 15s with hanging provider | asyncio.wait(timeout=15.0) in MoEScoringEngine.score() — pending tasks cancelled, done tasks aggregated |
| SC-3: `--rehearsal` CLI runs full demo cycle | RehearsalPipeline orchestrates SyntheticCapture + ReplayProvider through full event chain |
| SC-4: Dashboard rehearsal trigger | WebOperator handles "rehearsal" action, triggers RehearsalPipeline.run_demo() |

## Open Questions

1. **Groq JSON output reliability for scoring rubric format**
   - What we know: Groq supports `json_object` mode which guarantees valid JSON. The scoring prompt already says "output ONLY a JSON object" which satisfies the JSON mode requirement.
   - What's unclear: Whether `llama-3.3-70b-versatile` consistently produces the exact schema expected by `ScoringEngine._parse_and_validate()` (criteria array with name/score/justification fields). The roadmap explicitly flags this: "Groq JSON format reliability unknown until empirical testing."
   - Recommendation: Use `response_format={"type": "json_object"}` to guarantee valid JSON. The prompt already specifies the exact schema. Add a test with a manually verified Groq response. Start with neutral calibration and flag for empirical tuning.

2. **Optimal Groq model for scoring**
   - What we know: `llama-3.3-70b-versatile` is already used for commentary/QA. It supports JSON mode. Groq also offers `llama-3.1-8b-instant` (faster, less capable) and various other models.
   - What's unclear: Whether `llama-3.3-70b-versatile` produces adequately differentiated scores (avoids scoring everything 7.0 +-0.5).
   - Recommendation: Use `llama-3.3-70b-versatile` as default (matches existing Groq usage in codebase). Make the model configurable via `GroqProvider.__init__` parameter.

3. **Rehearsal mode theatrical timing**
   - What we know: Production theatrical flow uses `asyncio.sleep` delays (2s for score intro, 1.5s per criterion, 1s before total). Rehearsal should show this same flow.
   - What's unclear: Whether rehearsal should use the same delays (realistic but slow) or compressed delays (fast demo, 0.5x speed).
   - Recommendation: Use the same delays by default for operator training fidelity. Optionally accept a `--fast-rehearsal` flag that reduces all sleep durations by 4x.

4. **Rehearsal data persistence**
   - What we know: Production writes scorecards to `data/scores/`, memories to `data/observations/`, deliberation to `data/deliberation/`.
   - What's unclear: Whether rehearsal should write to the same directories (risk: polluting real data), a temp directory, or skip persistence.
   - Recommendation: Write to a dedicated `data/rehearsal/` directory that is auto-cleared on each rehearsal run. This allows operators to inspect rehearsal output without polluting production data.

## Sources

### Primary (HIGH confidence)
- `/groq/groq-python` (Context7) — Async client, JSON mode, OpenAI-compatible endpoint patterns
- `/websites/console_groq` (Context7) — Structured outputs, JSON mode, available models, API reference
- Codebase analysis — All provider implementations, MoE engine, scoring pipeline, E2E test patterns

### Secondary (MEDIUM confidence)
- Python `asyncio` stdlib documentation — `asyncio.wait` semantics, timeout behavior, task cancellation

### Tertiary (LOW confidence)
- Groq model calibration values — No empirical data available. Neutral defaults recommended with explicit "needs tuning" marker.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — All libraries already in project deps, Groq pattern proven in commentary layer
- Architecture: HIGH — Provider interface is established, MoE pattern clear, rehearsal pattern demonstrated in E2E tests
- GroqProvider implementation: HIGH — Direct copy of OpenAIProvider with `base_url` override
- MoE timeout (asyncio.wait): HIGH — Stdlib pattern, well-documented, straightforward replacement
- Groq calibration values: LOW — Empirical data needed, neutral defaults are starting point
- Rehearsal mode: MEDIUM — Architecture is clear from E2E test patterns, but requires new module integration with CLI/dashboard

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (stable domain, no fast-moving dependencies)
