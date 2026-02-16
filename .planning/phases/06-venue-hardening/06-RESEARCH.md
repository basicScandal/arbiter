# Phase 6: Venue Hardening - Research

**Researched:** 2026-02-16
**Domain:** Production resilience, TTS failover, graceful degradation, operator override, emotional TTS variety
**Confidence:** HIGH

## Summary

Phase 6 transforms Arbiter from a working prototype into a production system that survives a full 24-demo live event. The codebase already has solid error handling foundations -- every pipeline wraps LLM calls in try/except, fallback scorecards exist, commentary has a fallback string, and the Gemini session has a reconnection loop with resumption handles. What is missing is: (1) structured resilience patterns (retry with backoff, circuit breakers, health tracking), (2) TTS failover when Cartesia goes down, (3) explicit degraded-mode behavior paths, (4) operator pause/resume/override controls beyond the existing start/stop/reset lifecycle, and (5) expanded emotional variety in TTS beyond the current 3-emotion map (sarcastic/content/disappointed).

The critical insight is that this phase is NOT about adding new features -- it is about wrapping existing working components with resilience layers. The architecture is sound. The event bus pattern naturally supports degraded modes (if a subscriber fails, other subscribers still fire). The challenge is making each external dependency (Cartesia TTS, Gemini API, network) independently recoverable without operator intervention.

The system runs on macOS (Darwin 25.2.0). For TTS failover, the simplest reliable secondary provider is macOS `say` command via asyncio subprocess -- it is always available, requires zero configuration, and produces intelligible speech. This avoids adding a second cloud TTS dependency (ElevenLabs) that could also fail during the same network outage that took down Cartesia. For scenarios where network is up but Cartesia specifically is down, ElevenLabs REST API is the recommended cloud secondary.

**Primary recommendation:** Add a `tenacity`-based retry layer to all external API calls (Gemini, Cartesia). Implement a TTS failover chain (Cartesia WebSocket -> macOS `say` command). Add operator pause/resume commands to the TUI and CLI. Expand the emotion map from 3 emotions to 8+ using Cartesia's full emotion vocabulary. Track service health state per-component to enable smart degraded-mode decisions.

## Standard Stack

### Core (already installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | ~1.13 | Gemini API calls (commentary, scoring, deliberation) | Already in stack. Needs retry wrapping. |
| cartesia | ~3.0 | Primary TTS via WebSocket | Already in stack. Needs reconnection + failover. |
| fastapi | ~0.129 | Display server WebSocket | Already in stack. Already resilient (silent disconnect cleanup). |
| textual | ~1.0 | Operator TUI | Already in stack. Needs pause/resume bindings. |

### New Dependencies

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|-------------|
| tenacity | ~9.0 | Retry with exponential backoff + jitter for async API calls | De facto Python retry library. Native asyncio support. Decorates existing functions without restructuring. No new patterns needed. HIGH confidence (PyPI, GitHub verified). |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tenacity | Hand-rolled retry loops | tenacity handles jitter, backoff, stop conditions, async natively. Hand-rolling gets these wrong. |
| macOS `say` for TTS fallback | ElevenLabs as secondary cloud TTS | `say` works offline during network failures. ElevenLabs fails during same outage. Use `say` as last resort, not cloud secondary. |
| macOS `say` for TTS fallback | pyttsx3 | pyttsx3 wraps macOS NSSpeechSynthesizer (same engine as `say`) but adds a dependency and has no asyncio support. Direct subprocess `say` is simpler and equally capable on macOS. |
| Per-component health tracking | Global health boolean | Per-component allows partial degradation (e.g., TTS down but LLM up = text-only mode). Global boolean is too coarse. |

**Installation:**
```bash
uv add tenacity~=9.0
```

## Architecture Patterns

### Recommended Changes to Existing Structure

```
src/
+-- capture/              # Phase 1 (exists)
|   +-- gemini_session.py # ADD: tenacity retry on connect + send
|   +-- ...
+-- defense/              # Phase 2 (exists, no changes needed)
+-- commentary/           # Phase 3 (exists)
|   +-- tts_engine.py     # REFACTOR: add failover chain, reconnection
|   +-- tts_fallback.py   # NEW: macOS say fallback TTS provider
|   +-- generator.py      # ADD: tenacity retry on generate_content_stream
|   +-- pipeline.py       # ADD: degraded-mode text-only path when TTS is down
|   +-- ...
+-- scoring/              # Phase 4 (exists)
|   +-- engine.py         # ADD: tenacity retry on generate_content (already has fallback scorecard)
+-- memory/               # Phase 5 (exists)
|   +-- deliberation_engine.py  # ADD: tenacity retry on generate_content
+-- operator/             # Phase 1 (exists)
|   +-- tui.py            # ADD: pause/resume/override commands and keybindings
|   +-- cli.py            # ADD: pause/resume commands
+-- resilience/           # NEW: shared resilience utilities
|   +-- __init__.py
|   +-- health.py         # ServiceHealth tracker per component
|   +-- retry.py          # Shared tenacity retry configs
+-- main.py               # No changes needed
```

### Pattern 1: Tenacity Retry for Async API Calls

**What:** Wrap all external API calls (Gemini generate_content, Cartesia WebSocket send) with tenacity retry decorators. Use exponential backoff with jitter to avoid thundering herd. Stop after 3 attempts for interactive paths (commentary), 5 for background paths (scoring).

**When to use:** Every Gemini API call and Cartesia WebSocket operation.

**Example:**
```python
from tenacity import (
    retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
)

# Shared retry config for Gemini calls
GEMINI_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10, jitter=2),
    retry=retry_if_exception_type(
        (ConnectionError, TimeoutError, OSError)
    ),
    before_sleep=lambda rs: logger.warning(
        "Gemini retry attempt %d", rs.attempt_number,
    ),
)

# Apply to existing generator method
class CommentaryGenerator:
    @GEMINI_RETRY
    async def _call_gemini_stream(self, user_prompt: str) -> str:
        full_text = ""
        async for chunk in await self._client.aio.models.generate_content_stream(
            model=self._model, contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=PERSONA_PROMPT,
                max_output_tokens=500, temperature=0.8,
            ),
        ):
            if chunk.text:
                full_text += chunk.text
        return full_text
```

### Pattern 2: TTS Failover Chain

**What:** Add failover logic inside TTSEngine. Primary: Cartesia WebSocket. Fallback: macOS `say` via asyncio subprocess. The failover activates automatically when the primary raises an exception, with no operator intervention.

**When to use:** Every TTS speak operation.

**Example:**
```python
import asyncio
import shutil

class MacOSSayFallback:
    """Offline TTS fallback using macOS say command."""

    def __init__(self, voice: str = "Alex", rate: int = 200) -> None:
        self._voice = voice
        self._rate = rate
        self._available = shutil.which("say") is not None

    @property
    def available(self) -> bool:
        return self._available

    async def speak(self, text: str) -> None:
        if not self._available:
            logger.warning("macOS say not available, skipping speech")
            return
        proc = await asyncio.create_subprocess_exec(
            "say", "-v", self._voice, "-r", str(self._rate), text,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
```

The TTSEngine.speak method would try Cartesia first, catch exceptions, then
fall back to MacOSSayFallback.speak, and always publish TTSFinished in a
finally block (matching the existing pattern).

### Pattern 3: Service Health Tracker

**What:** A simple per-component health state tracker. Components report success/failure after each operation. Downstream code checks health state to make degradation decisions (e.g., skip TTS if unhealthy, use cached responses if LLM is slow).

**When to use:** Every external service interaction.

**Example:**
```python
import time

class ServiceHealth:
    """Tracks health status of external service dependencies."""

    def __init__(self, recovery_window: float = 60.0) -> None:
        self._healthy: dict[str, bool] = {}
        self._last_failure: dict[str, float] = {}
        self._failure_count: dict[str, int] = {}
        self._recovery_window = recovery_window

    def mark_healthy(self, service: str) -> None:
        self._healthy[service] = True
        self._failure_count[service] = 0

    def mark_unhealthy(self, service: str) -> None:
        self._healthy[service] = False
        self._last_failure[service] = time.time()
        self._failure_count[service] = self._failure_count.get(service, 0) + 1

    def is_healthy(self, service: str) -> bool:
        if service not in self._healthy:
            return True  # Assume healthy until proven otherwise
        if not self._healthy[service]:
            elapsed = time.time() - self._last_failure.get(service, 0)
            if elapsed > self._recovery_window:
                return True  # Allow retry after window
        return self._healthy[service]

    def get_status(self) -> dict[str, bool]:
        return {svc: self.is_healthy(svc) for svc in self._healthy}
```

### Pattern 4: Operator Pause/Resume

**What:** Add `pause` and `resume` commands to the demo state machine and operator interfaces. Pause suspends capture tasks (camera, audio stop producing) and Gemini session (stop sending). Resume restarts them. This is distinct from stop -- pause preserves the session, stop finalizes it.

**When to use:** When the operator needs to temporarily halt Arbiter (e.g., technical difficulty at venue, unplanned break).

**Example:**
```python
# Extend DemoMachine with pause/resume transitions
class DemoMachine(StateMachine):
    idle = State(initial=True)
    capturing = State()
    paused = State()      # NEW
    stopped = State()

    start_demo = idle.to(capturing)
    pause_demo = capturing.to(paused)     # NEW
    resume_demo = paused.to(capturing)    # NEW
    stop_demo = (
        capturing.to(stopped) | paused.to(stopped)  # stop from either
    )
    reset = stopped.to(idle)
```

### Pattern 5: Degraded Mode Decision Tree

**What:** When a component is unhealthy, the pipeline takes an alternative path rather than failing.

```
Commentary Generation:
  Gemini healthy? -> Generate normally
  Gemini unhealthy? -> Use cached fallback text

TTS Output:
  Cartesia healthy? -> Speak via Cartesia with emotions
  Cartesia unhealthy, macOS available? -> Speak via macOS say (no emotion)
  All TTS unhealthy? -> Text-only mode (display server still works)

Scoring:
  Gemini healthy? -> Score normally
  Gemini unhealthy? -> Fallback scorecard (5.0 across criteria) -- ALREADY EXISTS

Display Server:
  Always available (local, no external dependency)
```

### Anti-Patterns to Avoid

- **Retrying non-idempotent operations:** Gemini generate_content is idempotent (same prompt, new response). Cartesia TTS send is idempotent (re-send same text). Both are safe to retry. Do NOT retry state machine transitions.
- **Infinite retry loops:** Always set `stop_after_attempt`. An infinite retry on a down service blocks the entire pipeline for that demo.
- **Retry without jitter:** Multiple Arbiter components retrying Gemini simultaneously creates a thundering herd. Always use `wait_exponential_jitter`.
- **Failing to publish TTSFinished on fallback path:** The audio capture mute/unmute coordination depends on TTSSpeaking/TTSFinished events. The finally block MUST publish TTSFinished even when using the fallback TTS provider. The existing code already does this correctly.
- **Adding ElevenLabs as the only TTS fallback:** If network is down, both Cartesia and ElevenLabs fail. The fallback must be local/offline.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry with backoff | Custom while loops with sleep | tenacity decorators | Handles jitter, async sleep, exception filtering, attempt counting, callbacks. Hand-rolling misses edge cases. |
| TTS fallback speech | Custom audio synthesis | macOS `say` via asyncio subprocess | Always available on macOS, zero config, intelligible output. Not pretty but reliable. |
| Circuit breaker state | Custom failure counting | ServiceHealth class (simple, bespoke) | Full circuit breaker libraries (circuitbreaker, pyfailsafe) are overkill for 5 services. A 30-line health tracker suffices. |
| WebSocket reconnection | Custom reconnect loops | Already exists in GeminiSession.run() | The existing reconnect-with-resumption-handle pattern is correct. Add tenacity to individual send/receive operations, not the outer loop. |

**Key insight:** The codebase already has the right error-handling structure (try/except with fallbacks at every pipeline stage). Phase 6 adds *systematic* resilience (retry before fallback, health tracking for smart decisions, operator controls for manual intervention) on top of the existing *ad-hoc* resilience.

## Common Pitfalls

### Pitfall 1: Retry Storm Kills Gemini Quota

**What goes wrong:** All four Gemini clients (Live session, Commentary, Scoring, Deliberation) hit an outage simultaneously. Each retries 3x with short backoff. 12 requests hit the API in 10 seconds, triggering rate limiting that cascades.
**Why it happens:** No coordination between retry attempts across clients. No jitter.
**How to avoid:** Use `wait_exponential_jitter` with a generous jitter parameter (2-5 seconds). Stagger retry attempts naturally. Consider a shared rate limiter (asyncio.Semaphore) if Gemini 429s become frequent during testing.
**Warning signs:** Seeing multiple "retrying" log lines at the same timestamp from different components.

### Pitfall 2: TTS Fallback Blocks Event Loop

**What goes wrong:** macOS `say` is invoked synchronously, blocking the asyncio event loop for 5-10 seconds.
**Why it happens:** Developer uses synchronous subprocess call instead of asyncio subprocess.
**How to avoid:** Always use `asyncio.create_subprocess_exec("say", ...)` for the macOS fallback. This is non-blocking and awaitable.
**Warning signs:** UI freezes during fallback TTS. Events stop flowing. Textual TUI becomes unresponsive.

### Pitfall 3: Pause State Leaks Resources

**What goes wrong:** Operator pauses demo. Camera and audio streams are paused but PyAudio/OpenCV resources stay open. After 10 minutes, OS reclaims the audio device. Resume fails.
**Why it happens:** Pause implemented as "stop sending data" but hardware resources stay allocated.
**How to avoid:** Pause should mute audio (already works -- just set `_muted = True`) and pause camera (set a `_paused` flag, skip frame capture but keep the cv2.VideoCapture open). Do NOT close and reopen hardware resources on pause/resume -- that is fragile.
**Warning signs:** Resume after long pause fails with "device busy" or "stream not open" errors.

### Pitfall 4: Health Recovery Window Too Short

**What goes wrong:** Cartesia goes down. Health tracker marks unhealthy. 5 seconds later, recovery window expires, next speak attempt tries Cartesia again (still down), fails, marks unhealthy again. Rapid oscillation.
**Why it happens:** Recovery window is too short for typical cloud service outages.
**How to avoid:** Set recovery window to 60 seconds minimum. For venue conditions, 120 seconds is safer. Exponentially increase recovery window on repeated failures (1min, 2min, 4min, cap at 10min).
**Warning signs:** Log shows rapid alternation between "TTS failed" and "TTS recovered" within seconds.

### Pitfall 5: Emotion Map Does Not Cover Arbiter's Full Range

**What goes wrong:** Arbiter generates commentary with surprise, irony, or genuine admiration, but the emotion map only has 3 options (sarcastic/content/disappointed). All nuanced emotions collapse to "sarcastic" default.
**Why it happens:** Phase 3 implemented a minimal emotion map. Phase 6 requirement PERS-04 demands emotional variety.
**How to avoid:** Expand the keyword-to-emotion map using Cartesia's full emotion vocabulary. Map at least: sarcastic, ironic, contempt, surprised/amazed, disappointed, content, excited, confident, skeptical. Use Cartesia's primary emotions (neutral, angry, excited, content, sad, scared) plus secondary emotions that match the persona.
**Warning signs:** All sentences spoken with the same tone regardless of content.

## Code Examples

### Tenacity Retry on Async Gemini Call

```python
# Source: tenacity docs (https://tenacity.readthedocs.io) + google-genai SDK
from tenacity import (
    retry, stop_after_attempt, wait_exponential_jitter,
    retry_if_exception_type,
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10, jitter=2),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
)
async def _generate_with_retry(client, model, contents, config):
    """Wrap Gemini generate_content with retry."""
    response = await client.aio.models.generate_content(
        model=model, contents=contents, config=config,
    )
    return response
```

### macOS Say Fallback TTS

```python
# Source: macOS say command, asyncio subprocess
import asyncio
import shutil

async def speak_macos_say(
    text: str, voice: str = "Alex", rate: int = 210,
) -> None:
    """Speak text using macOS say command as TTS fallback."""
    if not shutil.which("say"):
        return
    proc = await asyncio.create_subprocess_exec(
        "say", "-v", voice, "-r", str(rate), "--", text,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
```

### Expanded Emotion Map

```python
# Source: Cartesia Sonic 3 emotion list (Context7 /websites/cartesia_ai)
# Primary emotions (best quality): neutral, angry, excited, content, sad, scared
# Relevant secondary: sarcastic, ironic, contempt, surprised, amazed,
#   disappointed, confident, skeptical, curious, proud, disgusted

_EMOTION_KEYWORDS: dict[str, list[str]] = {
    "sarcastic": [
        "bold strategy", "interesting choice", "somehow", "mysteriously",
        "apparently", "clearly", "of course",
    ],
    "ironic": ["ironic", "irony", "ironically", "paradox"],
    "contempt": [
        "pathetic", "embarrassing", "lazy", "half-baked", "amateur",
    ],
    "surprised": [
        "actually", "genuinely", "surprisingly", "didn't expect",
        "impressed", "wow",
    ],
    "amazed": [
        "incredible", "remarkable", "exceptional", "brilliant", "stunning",
    ],
    "disappointed": [
        "unfortunately", "shame", "disaster", "terrible", "awful",
        "missing", "broken", "failed", "crashed",
    ],
    "content": [
        "solid", "clean", "elegant", "respect", "well-built", "thoughtful",
    ],
    "excited": ["love", "amazing", "fantastic", "breakthrough"],
    "confident": [
        "clearly the best", "no question", "without doubt", "winner",
    ],
    "skeptical": [
        "claims", "supposedly", "allegedly", "in theory",
        "if we believe", "questionable",
    ],
    "curious": ["interesting", "intriguing", "wonder", "how did"],
    "proud": ["now that", "that's what", "exactly right", "nailed"],
}

def classify_emotion(sentence: str) -> str:
    """Classify sentence emotion using keyword matching."""
    lower = sentence.lower()
    for emotion, keywords in _EMOTION_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return emotion
    return "sarcastic"  # Arbiter default persona tone
```

### Operator Pause/Resume Keybindings

```python
# Added to ArbiterTUI.BINDINGS
BINDINGS = [
    Binding("ctrl+s", "prefill_start", "Start", show=True),
    Binding("ctrl+x", "send_stop", "Stop", show=True),
    Binding("ctrl+p", "send_pause", "Pause", show=True),    # NEW
    Binding("ctrl+o", "send_resume", "Resume", show=True),   # NEW
    Binding("ctrl+r", "send_reset", "Reset", show=True),
    Binding("ctrl+q", "quit_app", "Quit", show=True),
]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Bare try/except with hardcoded sleep | tenacity decorators with exponential backoff + jitter | Standard since 2020, widely adopted by 2024 | Eliminates hand-rolled retry bugs, adds observability |
| Single TTS provider, fail = silence | Failover chain with offline fallback | Established pattern in production voice apps | System speaks even during network outage |
| Binary healthy/unhealthy | Timed recovery windows with exponential backoff | Standard circuit breaker evolution | Prevents rapid oscillation, allows automatic recovery |
| 3 TTS emotions (sarcastic/content/disappointed) | 12+ emotions from Cartesia Sonic 3 vocabulary | Cartesia Sonic 3 (2025) full emotion list | Commentary sounds varied and appropriate to content |

**Deprecated/outdated:**
- pyttsx3 for macOS fallback: Wraps the same NSSpeechSynthesizer as `say` but adds a dependency. Direct subprocess is simpler.
- Using a second cloud TTS (ElevenLabs) as sole failover: Fails during network outage. Must have offline option.

## Open Questions

1. **Cartesia WebSocket reconnection behavior**
   - What we know: The current TTSEngine creates a single WebSocket connection at startup via `websocket_connect().enter()`. If the connection drops mid-event, speaks fail and fall through to the except block.
   - What's unclear: Whether Cartesia SDK has built-in reconnection, or if we need to detect the closed connection and re-call `websocket_connect().enter()`.
   - Recommendation: Add a `_ensure_connected()` method that checks connection state before each speak, and reconnects if needed. Wrap in tenacity retry. LOW risk -- the existing try/except already catches failures; this just adds recovery.

2. **Gemini Live API session recovery after network blip**
   - What we know: GeminiSession already has a reconnection loop with resumption handles. If the WebSocket drops, it reconnects with the stored handle.
   - What's unclear: Whether a brief network blip (2-5 seconds) causes a full session disconnect or if the WebSocket has its own keepalive.
   - Recommendation: The existing reconnection loop is correct. Add tenacity retry to individual `send_realtime_input` calls within the send loop to handle transient errors without triggering full reconnection. Test with simulated network interruption.

3. **macOS `say` voice selection for venue**
   - What we know: macOS has many voices. "Alex" is the default high-quality English male voice. "Daniel" (British) might better match Arbiter's Simon Cowell persona.
   - What's unclear: Which voice sounds best through a venue PA system.
   - Recommendation: Test "Alex", "Daniel", and "Tom" at the venue during setup. Store in config as `TTS_FALLBACK_VOICE`. Default to "Alex".

4. **Operator override during active commentary**
   - What we know: The operator can start/stop/reset demos. But what if Arbiter is mid-commentary and the operator wants to skip to the next team?
   - What's unclear: Whether "stop" during commentary should cut TTS immediately or let it finish.
   - Recommendation: Add a `skip` command that cancels in-progress TTS and clears the display. Separate from `stop` (which ends the demo session). This gives the operator an "abort commentary" escape hatch.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: All 44 Python source files in `src/` read and analyzed
- Context7: `/cartesia-ai/cartesia-python` -- WebSocket TTS connection, error handling patterns
- Context7: `/websites/cartesia_ai` -- Sonic 3 full emotion list (60+ emotions), generation_config parameters, speed/volume control
- Cartesia Sonic 3 emotion docs: Primary emotions (neutral, angry, excited, content, sad, scared) plus full secondary list verified via Context7

### Secondary (MEDIUM confidence)
- tenacity library: [PyPI](https://pypi.org/project/tenacity/), [GitHub](https://github.com/jd/tenacity) -- async retry decorator, exponential backoff with jitter, stop conditions
- macOS `say` command: Built-in on all macOS versions, used via asyncio.create_subprocess_exec
- [Production asyncio patterns](https://timderzhavets.com/blog/taming-asyncio-production-patterns-that-prevent-silent/) -- graceful shutdown, deadline propagation, health monitoring
- [Circuit breaker patterns](https://pypi.org/project/circuitbreaker/) -- pattern reference (not used directly; bespoke ServiceHealth preferred)

### Tertiary (LOW confidence)
- ElevenLabs as alternative cloud TTS: Not recommended as sole failover due to shared network dependency. Could be added as a middle tier (Cartesia -> ElevenLabs -> macOS say) but adds complexity and a new SDK dependency. Defer unless venue testing reveals need.
- Optimal recovery window durations (60s, 120s): Based on general production experience, not Arbiter-specific testing. Tune during venue rehearsal.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- tenacity is the de facto Python retry library. macOS `say` is always available on the target platform. No risky new dependencies.
- Architecture: HIGH -- The existing architecture naturally supports resilience layers. Event bus decoupling means component failures are isolated. All patterns are additive (wrapping existing code), not restructuring.
- Pitfalls: HIGH -- Based on direct codebase analysis. Every pitfall maps to a specific existing code pattern that needs hardening.
- Emotion expansion: HIGH -- Cartesia full emotion list verified via Context7. Keyword matching is the same pattern already used in generator.py, just with more entries.
- Operator controls: MEDIUM -- Pause/resume state machine extension is straightforward (python-statemachine supports it), but the interaction between pause and in-progress async tasks (TTS, scoring) needs careful implementation to avoid orphaned tasks.

**Research date:** 2026-02-16
**Valid until:** 2026-03-16 (30 days -- all dependencies are stable, Cartesia API is versioned, tenacity is mature)
