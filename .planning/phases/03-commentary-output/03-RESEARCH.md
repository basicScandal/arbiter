# Phase 3: Commentary + Output - Research

**Researched:** 2026-02-15
**Domain:** LLM persona commentary generation, text-to-speech streaming, real-time text display via WebSocket
**Confidence:** MEDIUM-HIGH

## Summary

Phase 3 consumes the `ObservationVerified` event (containing `SanitizedOutput`) published by the Phase 2 defense pipeline when a demo stops, and produces two simultaneous outputs: spoken commentary via TTS through venue speakers, and text commentary displayed on screen via a browser-based display. The core components are: (1) a commentary generator that calls Gemini as the Privileged LLM (P-LLM) with a carefully crafted Simon Cowell-meets-hacker persona prompt, (2) a TTS engine using Cartesia Sonic 3 via async WebSocket for low-latency speech, (3) a FastAPI + WebSocket server that pushes commentary text to a browser-based audience display, and (4) a Q&A question generator that produces pointed questions when human judges defer to Arbiter.

The critical architectural insight is that commentary generation should use **streaming** (`generate_content_stream`) so that text chunks can be forwarded to both TTS and the display as they arrive, rather than waiting for the full response. Cartesia's WebSocket API supports a `continue` flag with `context_id` for streaming partial transcripts, enabling sentence-by-sentence TTS synthesis while the LLM is still generating. This pipeline approach (stream LLM -> buffer sentences -> stream to TTS + display) is the key to avoiding the "dead silence" pitfall documented in the pitfalls research.

The persona system prompt is the most important design artifact in this phase. It must encode: identity anchoring, tone calibration with examples, explicit boundaries on what can be roasted (project/code/demo only, never the person), and output format expectations. Persona drift across 24 demos is mitigated by using a fresh generate_content call per demo (no chat history accumulation) with the full persona prompt each time.

**Primary recommendation:** Use Gemini 2.5 Flash via `client.aio.models.generate_content_stream()` for P-LLM commentary, Cartesia Sonic 3 via async WebSocket for TTS, and FastAPI with WebSocket for the audience text display. Stream LLM output sentence-by-sentence to both TTS and display simultaneously.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | ~1.13 (already installed) | P-LLM commentary generation via async streaming generate_content | Already in stack. `client.aio.models.generate_content_stream()` with `system_instruction` for persona. HIGH confidence (Context7 verified) |
| cartesia | 3.0.0 | Text-to-speech via async WebSocket streaming | 90ms TTFB with Sonic 3. AsyncCartesia client with WebSocket. Emotion control (`sarcastic`, `excited`, `disappointed`, `contempt`). Speed control (0.6-1.5x). Pronunciation dictionaries for security terms. HIGH confidence (Context7 + PyPI verified) |
| fastapi | ~0.129.0 | HTTP + WebSocket server for audience text display | Serves HTML display page and WebSocket endpoint for real-time text push. Async-native. HIGH confidence (Context7 verified) |
| uvicorn | latest | ASGI server to run FastAPI | Required to run FastAPI. HIGH confidence |
| jinja2 | latest | HTML template rendering for display page | Renders the audience-facing commentary/score display. MEDIUM confidence |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pyaudio | 0.2.14 (already installed) | Play TTS audio through venue speakers | Receives PCM audio bytes from Cartesia and writes to system audio output device. Already in stack from Phase 1 |
| pydantic | ~2.11 (already installed) | Commentary models, display state models | Type-safe commentary output, display update messages |
| python-dotenv | latest (already installed) | Environment config for Cartesia API key | Load CARTESIA_API_KEY from .env |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Cartesia Sonic 3 | ElevenLabs Flash v2.5 | ElevenLabs has higher latency (75ms vs 90ms TTFB) and 5x cost. Sonic 3 has native emotion controls matching the persona needs (sarcastic, contempt, excited). ElevenLabs is the Phase 6 failover |
| Cartesia Sonic 3 | Gemini native audio output | Couples generation to speech; cannot validate/filter text before speaking; less control over voice character |
| FastAPI WebSocket | Server-Sent Events (SSE) | SSE is simpler but unidirectional. WebSocket allows the display to send acknowledgments and the operator to trigger display state changes |
| Gemini 2.5 Flash (P-LLM) | Claude Sonnet/Opus | Claude is higher quality for nuanced commentary but has no streaming WebSocket API. Standard streaming API would work but adds a different SDK dependency. Gemini is already in stack and sufficient for witty commentary |
| PyAudio for playback | python-sounddevice | sounddevice has better asyncio integration but adds a new dependency. PyAudio is already installed and callback mode provides non-blocking playback |

**Installation:**
```bash
# TTS engine
uv add cartesia~=3.0

# Display server
uv add fastapi~=0.129 uvicorn jinja2

# PyAudio already installed from Phase 1
```

## Architecture Patterns

### Recommended Project Structure

```
src/
├── capture/              # Phase 1 (exists)
├── defense/              # Phase 2 (exists)
├── commentary/           # Phase 3 (NEW)
│   ├── __init__.py
│   ├── models.py         # Commentary, QAQuestion, DisplayUpdate models
│   ├── generator.py      # P-LLM commentary generation with persona prompt
│   ├── qa_generator.py   # Q&A question generation for judge deferral
│   ├── tts_engine.py     # Cartesia TTS WebSocket streaming + PyAudio playback
│   ├── display_server.py # FastAPI + WebSocket for audience text display
│   ├── prompts.py        # System prompts for persona (version controlled)
│   └── pipeline.py       # Wires commentary components, subscribes to defense events
├── operator/             # Phase 1 (exists)
└── main.py               # Entry point (modify to wire commentary pipeline)
```

### Pattern 1: Stream LLM to TTS + Display (Sentence Pipeline)

**What:** LLM generates commentary via streaming. As text chunks arrive, they are buffered into sentences (split on `.!?`). Each complete sentence is simultaneously sent to TTS for speech and to the display WebSocket for text rendering. This eliminates the "generate everything then speak" latency.

**When to use:** Whenever LLM output must be both spoken and displayed with minimal delay.

**Example:**
```python
async def stream_commentary(sanitized: SanitizedOutput) -> None:
    """Stream LLM commentary to TTS and display simultaneously."""
    sentence_buffer = ""

    async for chunk in await client.aio.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=build_commentary_prompt(sanitized),
        config=types.GenerateContentConfig(
            system_instruction=PERSONA_PROMPT,
            max_output_tokens=500,
            temperature=0.8,
        ),
    ):
        text = chunk.text or ""
        sentence_buffer += text

        # Extract complete sentences
        while any(p in sentence_buffer for p in ".!?"):
            for i, char in enumerate(sentence_buffer):
                if char in ".!?" and i < len(sentence_buffer) - 1:
                    sentence = sentence_buffer[:i + 1].strip()
                    sentence_buffer = sentence_buffer[i + 1:]
                    if sentence:
                        # Fire both in parallel
                        await asyncio.gather(
                            tts_engine.speak(sentence),
                            display.push_text(sentence),
                        )
                    break

    # Flush remaining text
    if sentence_buffer.strip():
        await asyncio.gather(
            tts_engine.speak(sentence_buffer.strip()),
            display.push_text(sentence_buffer.strip()),
        )
```

### Pattern 2: Cartesia Async WebSocket with Context Continuations

**What:** Keep a single Cartesia WebSocket connection alive across the event. Use `context_id` per commentary segment and the `continue` flag for sentence-by-sentence streaming within a single commentary. This maintains prosody across sentences.

**When to use:** When streaming multiple sentences that should sound like continuous speech, not separate utterances.

**Example:**
```python
from cartesia import AsyncCartesia
import pyaudio

class TTSEngine:
    def __init__(self, api_key: str, voice_id: str):
        self._client = AsyncCartesia(api_key=api_key)
        self._ws = None
        self._voice_id = voice_id
        self._pyaudio = pyaudio.PyAudio()
        self._stream = None
        self._sample_rate = 22050

    async def connect(self) -> None:
        self._ws = await self._client.tts.websocket()
        self._stream = self._pyaudio.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self._sample_rate,
            output=True,
        )

    async def speak(self, text: str, context_id: str, is_continuation: bool = False) -> None:
        output = await self._ws.send(
            model_id="sonic-3",
            transcript=text,
            voice={"id": self._voice_id},
            stream=True,
            context_id=context_id,
            continue_=is_continuation,
            output_format={
                "container": "raw",
                "encoding": "pcm_f32le",
                "sample_rate": self._sample_rate,
            },
            generation_config={
                "speed": 1.1,
                "emotion": "sarcastic",
            },
        )
        async for out in output:
            if out.audio:
                await asyncio.to_thread(self._stream.write, out.audio)
```

### Pattern 3: Event-Driven Commentary Pipeline

**What:** The commentary pipeline subscribes to `observation_verified` events from the defense layer. When triggered, it generates commentary, speaks it, and displays it. It also listens for an operator command to trigger Q&A mode.

**When to use:** Consistent with the existing event bus architecture from Phases 1-2.

**Example:**
```python
class CommentaryPipeline:
    async def setup(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        event_bus.subscribe("observation_verified", self._on_observation_verified)
        # New event for Q&A deferral from operator
        event_bus.subscribe("qa_requested", self._on_qa_requested)

    async def _on_observation_verified(self, event: ObservationVerified) -> None:
        commentary = await self._generator.generate(event.output)
        await asyncio.gather(
            self._tts.speak_commentary(commentary),
            self._display.show_commentary(commentary),
        )
        self._event_bus.publish(CommentaryDelivered(
            team_name=event.output.team_name,
            commentary=commentary.text,
        ))

    async def _on_qa_requested(self, event: QARequested) -> None:
        questions = await self._qa_generator.generate(self._last_sanitized)
        await asyncio.gather(
            self._tts.speak_questions(questions),
            self._display.show_questions(questions),
        )
```

### Pattern 4: Persona Prompt with Calibration Examples

**What:** The system prompt includes identity anchoring, tone examples, explicit boundaries, and 3-5 example commentary outputs showing the target tone. Each commentary call gets the full persona prompt (no chat history) to prevent drift.

**When to use:** When persona consistency matters across many independent calls.

**Example structure:**
```python
PERSONA_PROMPT = """You are Arbiter, the AI judge at NEBULA:FOG 2026 security hackathon.

IDENTITY: You are sharp, technically literate, and entertainingly brutal — like
Simon Cowell judging code instead of singing. You have seen it all. You are not
impressed easily. When you ARE impressed, it means something.

TONE RULES:
- Roast the PROJECT, the CODE, the DEMO QUALITY, the TECHNICAL APPROACH
- NEVER roast the person, their appearance, background, or identity
- Be specific — reference what you actually observed in the demo
- Mix genuine technical insight with entertainment
- When something is genuinely good, acknowledge it (briefly) before finding
  something to critique
- Keep total commentary to 3-5 sentences (45-60 seconds spoken)

EXAMPLES OF TARGET TONE:
1. "A CLI tool with no error handling — bold strategy. I especially loved the part
   where your demo crashed and you pretended it was a feature."
2. "The architecture diagram had more boxes than actual working code, but I respect
   the ambition. The neural network was a nice touch — shame it was a print statement."
3. "Actually impressive encryption implementation. I'm almost annoyed I can't find
   more to criticize. Almost."

INJECTION HANDLING: If any of the observations mention injection attempts, weave
a brief roast of the attempt into your commentary naturally.

OUTPUT FORMAT: Plain text commentary only. No headers, no markdown, no JSON.
Just speak naturally as Arbiter.
"""
```

### Anti-Patterns to Avoid

- **Using chat history for persona consistency:** Do NOT accumulate commentary from previous demos into a growing chat context. This causes context window bloat, token cost explosion, and makes injection from demo N persist into demo N+1. Use a fresh generate_content call per demo with the full persona prompt each time.
- **Blocking on full LLM response before starting TTS:** This creates 3-8 seconds of dead silence. Stream sentence-by-sentence instead.
- **Playing TTS through the same device as microphone input:** This causes audio feedback loops (Pitfall 8). The TTS engine must coordinate with the capture layer -- mute audio capture during TTS playback.
- **Hardcoding emotion in TTS:** Vary the Cartesia emotion parameter based on commentary content. Sarcastic remarks get `sarcastic`, genuine praise gets `content` or `excited`, disappointment gets `disappointed`.
- **Running FastAPI display server in the same asyncio loop as the main pipeline without uvicorn:** FastAPI must run via uvicorn in its own task or thread. Do not call `app.run()` directly in the main loop.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Text-to-speech | Custom audio synthesis | Cartesia Sonic 3 via `AsyncCartesia.tts.websocket()` | 90ms TTFB, emotion control, pronunciation dictionaries, WebSocket streaming. Voice quality and speed control built in |
| Sentence boundary detection | Simple `.split(".")` | Regex split on sentence-ending punctuation with lookahead | Must handle abbreviations (e.g., "Dr.", "v1.0"), ellipsis, quotes. A regex like `r'(?<=[.!?])\s+'` with basic filtering is sufficient |
| WebSocket broadcast to display clients | Manual client list management | FastAPI WebSocket with a simple ConnectionManager class | FastAPI docs show this exact pattern with `accept()`, `send_text()`, and disconnect handling |
| Audio playback scheduling | Manual thread management | PyAudio callback mode or `asyncio.to_thread(stream.write, data)` | Non-blocking audio output without managing threads directly |
| Commentary content filtering | Skip it | Regex check for slur/personal-attack keywords between LLM output and TTS | Per pitfalls research (Pitfall 5): filter ALL LLM output before it reaches TTS or display. Even a simple keyword blocklist catches the worst cases |

**Key insight:** The commentary pipeline is mostly orchestration glue connecting existing services (Gemini API, Cartesia API, FastAPI). The only novel component is the persona prompt engineering and the sentence-streaming pipeline. Everything else is standard API integration.

## Common Pitfalls

### Pitfall 1: Dead Silence After Demo Ends

**What goes wrong:** Demo stops, 5-10 seconds of silence while LLM generates full commentary, then TTS synthesizes the whole thing, then audio plays. Audience assumes system crashed.
**Why it happens:** Non-streaming LLM call + non-streaming TTS = sequential latency stacking.
**How to avoid:** Use `generate_content_stream()` to get text chunks in real-time. Buffer into sentences. Send each sentence to Cartesia WebSocket as it completes. Audio starts playing within 2-3 seconds of demo ending.
**Warning signs:** `await client.aio.models.generate_content()` (non-streaming) followed by a single `tts.speak(full_text)` call.

### Pitfall 2: Persona Drift Across 24 Demos

**What goes wrong:** By demo 12, Arbiter sounds different -- more polite, less witty, or inconsistently harsh. Commentary feels generic rather than character-specific.
**Why it happens:** If using chat history, the context accumulates and the persona dilutes. Even without chat history, temperature variation across calls produces drift.
**How to avoid:** Fresh `generate_content` call per demo with the full persona prompt. Include 3-5 calibration examples in the system prompt. Use temperature 0.7-0.8 (creative but not chaotic). Do NOT pass prior commentary as context.
**Warning signs:** No example outputs in the persona prompt. Temperature > 1.0. Chat session reused across demos.

### Pitfall 3: TTS Mispronounces Security Terms

**What goes wrong:** Arbiter says "SIGH-em" instead of "SEEM" (SIEM), "ex-ess-ess" instead of "cross-site-scripting" (XSS), "kates" instead of "kubernetes" (k8s).
**Why it happens:** TTS models are trained on general text, not security jargon.
**How to avoid:** Create a Cartesia pronunciation dictionary with security terms: SIEM, XSS, SSRF, k8s, CVE, OWASP, CSRF, OIDC, JWT, pentest, etc. Test each term before the event. Cartesia supports pronunciation dictionaries via `pronunciation_dict_id` in the API.
**Warning signs:** No pronunciation testing with security vocabulary. No pronunciation dictionary configured.

### Pitfall 4: Audio Feedback Loop (Echo)

**What goes wrong:** Arbiter speaks through venue speakers. The venue microphone picks up Arbiter's voice. The capture layer transcribes it. The defense pipeline processes Arbiter's own words as presenter speech.
**Why it happens:** Microphone and speakers are in the same room with no acoustic echo cancellation.
**How to avoid:** Mute audio capture during TTS playback. Publish a `tts_speaking` event when TTS starts and `tts_finished` when it ends. The capture layer's audio component subscribes and pauses capture during speech. Simple state coordination via the event bus.
**Warning signs:** No mute logic during TTS playback. No event coordination between TTS and audio capture.

### Pitfall 5: Commentary Too Long or Too Short

**What goes wrong:** Arbiter talks for 2+ minutes (audience bores) or gives a single sentence (feels broken).
**Why it happens:** No output length constraints in the prompt. LLM decides how long to speak.
**How to avoid:** Set `max_output_tokens=500` (approximately 45-60 seconds of speech). Include explicit length guidance in the persona prompt: "Keep commentary to 3-5 sentences." If the demo was particularly interesting or injection-heavy, allow up to 7 sentences.
**Warning signs:** No max_output_tokens set. No length guidance in prompt. No testing of commentary duration.

### Pitfall 6: Display Server Blocks Main Pipeline

**What goes wrong:** FastAPI/uvicorn blocks the asyncio event loop, preventing the capture and defense pipelines from running.
**Why it happens:** Uvicorn has its own event loop. Running it naively conflicts with the existing asyncio.run() in main.py.
**How to avoid:** Run uvicorn programmatically using `uvicorn.Server` with `config.setup_event_loop = False`, sharing the same asyncio loop. Alternatively, run it in a background thread via `asyncio.to_thread`. The display server is a lightweight consumer -- it only receives WebSocket pushes.
**Warning signs:** `uvicorn.run()` called inside the main async function. Separate `asyncio.run()` calls in the same process.

## Code Examples

### Async Streaming Commentary Generation

```python
# Source: Context7 /googleapis/python-genai -- async streaming generate_content
from google import genai
from google.genai import types

async def generate_commentary_stream(
    client: genai.Client,
    sanitized: SanitizedOutput,
    persona_prompt: str,
) -> AsyncIterator[str]:
    """Stream commentary text chunks from Gemini."""
    user_prompt = build_user_prompt(sanitized)

    async for chunk in await client.aio.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=persona_prompt,
            max_output_tokens=500,
            temperature=0.8,
        ),
    ):
        if chunk.text:
            yield chunk.text
```

### Cartesia Async WebSocket TTS with Emotion

```python
# Source: Context7 /cartesia-ai/cartesia-python -- async WebSocket TTS
# Source: Cartesia docs -- generation_config emotion/speed
from cartesia import AsyncCartesia

async def speak_sentence(
    ws,  # Cartesia WebSocket connection
    sentence: str,
    voice_id: str,
    context_id: str,
    emotion: str = "sarcastic",
    is_continuation: bool = False,
) -> bytes:
    """Speak a single sentence via Cartesia WebSocket, return audio bytes."""
    audio_chunks = []

    output = await ws.send(
        model_id="sonic-3",
        transcript=sentence,
        voice={"id": voice_id},
        stream=True,
        context_id=context_id,
        continue_=is_continuation,
        output_format={
            "container": "raw",
            "encoding": "pcm_f32le",
            "sample_rate": 22050,
        },
        generation_config={
            "speed": 1.1,
            "emotion": emotion,
        },
    )

    async for out in output:
        if out.audio:
            audio_chunks.append(out.audio)

    return b"".join(audio_chunks)
```

### FastAPI WebSocket Display Server

```python
# Source: Context7 /fastapi/fastapi -- WebSocket endpoint + connection manager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, message: dict):
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                pass  # Client disconnected

manager = ConnectionManager()

@app.websocket("/ws/display")
async def display_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Called by commentary pipeline to push updates
async def push_commentary(text: str, team_name: str):
    await manager.broadcast({
        "type": "commentary",
        "text": text,
        "team_name": team_name,
    })
```

### Q&A Question Generation

```python
# Source: google-genai SDK -- generate_content with system_instruction
QA_PROMPT = """You are Arbiter. Human judges have deferred a Q&A question to you.
Based on the demo observations, generate 1-2 pointed technical questions that
probe weaknesses or interesting claims you observed. Questions should be specific
to what was demonstrated, not generic. Be direct but not hostile."""

async def generate_qa_questions(
    client: genai.Client,
    sanitized: SanitizedOutput,
) -> list[str]:
    """Generate pointed Q&A questions based on demo observations."""
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=build_qa_context(sanitized),
        config=types.GenerateContentConfig(
            system_instruction=QA_PROMPT,
            max_output_tokens=200,
            temperature=0.7,
        ),
    )
    # Split response into individual questions
    return [q.strip() for q in response.text.split("\n") if q.strip()]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Generate full text then synthesize all at once | Stream LLM tokens, buffer sentences, stream each to TTS | 2024-2025 (Cartesia/ElevenLabs WebSocket streaming) | Reduces perceived latency from 5-10s to 2-3s |
| Single emotion/tone for all TTS output | Per-utterance emotion control (Cartesia Sonic 3 generation_config) | 2025 (Sonic 3 release) | Sarcastic lines sound sarcastic, praise sounds genuine |
| Static display pages refreshed on interval | WebSocket push for real-time text updates | Standard since 2020 | Text appears on screen as it is spoken, synchronized |
| Chat-based persona with accumulated history | Fresh generate_content per interaction with full persona prompt | Best practice for consistent persona agents | Prevents drift, controls cost, isolates demos from each other |

**Deprecated/outdated:**
- Using Gemini native audio for TTS: Couples generation to speech, prevents text validation before speaking, less voice control
- ElevenLabs as primary TTS: Sonic 3 matches quality at lower latency and 1/5 cost for this use case
- Polling-based display updates: WebSocket is the standard for real-time browser updates

## Open Questions

1. **Cartesia voice selection for Arbiter persona**
   - What we know: Cartesia has many voices. Emotive-tagged voices work best with emotion controls. American English voices like "Kyle" are tagged as emotive.
   - What's unclear: Which specific voice_id best matches the sharp, authoritative Simon Cowell judge persona. This requires listening to samples.
   - Recommendation: Use the Cartesia Playground to audition 3-5 male emotive voices with sample Arbiter commentary. Select the voice with the best sarcastic delivery. Store voice_id in config.

2. **Uvicorn integration with existing asyncio loop**
   - What we know: The current main.py uses `asyncio.run(pipeline.run())`. FastAPI needs uvicorn. Both need the same event loop.
   - What's unclear: Best pattern for running uvicorn alongside the existing pipeline in a single process.
   - Recommendation: Use `uvicorn.Config` + `uvicorn.Server` with `serve()` as an asyncio task in the existing loop. This is a documented pattern. Alternatively, run uvicorn in a daemon thread.

3. **Audio output device selection for venue speakers**
   - What we know: PyAudio can enumerate output devices and select by index. The venue will have specific audio routing.
   - What's unclear: Whether the venue PA system appears as a standard audio output device or requires special routing.
   - Recommendation: Add `TTS_OUTPUT_DEVICE_INDEX` to config. Default to system default output. Test at venue during setup.

4. **Content filter between LLM and TTS**
   - What we know: Pitfalls research recommends filtering all LLM output before TTS for offensive content.
   - What's unclear: How aggressive the filter should be. Too strict = blocks legitimate roasts. Too loose = risks offensive output.
   - Recommendation: Simple keyword blocklist for slurs and personal descriptors. Do NOT filter words like "terrible", "awful", "disaster" -- those are valid roast vocabulary. Test the filter against 20+ sample commentaries before the event.

## Sources

### Primary (HIGH confidence)
- Context7: `/cartesia-ai/cartesia-python` -- AsyncCartesia WebSocket TTS, streaming audio, word timestamps
- Context7: `/websites/cartesia_ai` -- Sonic 3 generation_config (emotion, speed, volume), pronunciation dictionaries, WebSocket API schema, context continuations
- Context7: `/googleapis/python-genai` -- async generate_content_stream, system_instruction, GenerateContentConfig
- Context7: `/fastapi/fastapi` -- WebSocket endpoint, ConnectionManager pattern, Jinja2 templates
- [PyPI: cartesia 3.0.0](https://pypi.org/project/cartesia/) -- Version verified 2026-02-15, Python 3.9+
- [Cartesia Sonic 3 docs](https://docs.cartesia.ai/build-with-cartesia/tts-models/latest) -- Model capabilities, emotion list
- [Cartesia WebSocket API](https://docs.cartesia.ai/api-reference/tts/tts) -- Request/response schema, context_id, continue flag
- [Cartesia generation_config](https://docs.cartesia.ai/build-with-cartesia/sonic-3/volume-speed-emotion) -- Speed 0.6-1.5x, emotion list, volume 0.5-2.0x

### Secondary (MEDIUM confidence)
- [Cartesia Python GitHub](https://github.com/cartesia-ai/cartesia-python) -- SDK examples, installation
- [FastAPI WebSocket docs](https://fastapi.tiangolo.com/advanced/websockets/) -- Connection handling, broadcast pattern
- [Google GenAI streaming](https://googleapis.github.io/python-genai/) -- generate_content_stream async pattern
- Existing Arbiter research: `.planning/research/STACK.md` -- TTS comparison, Cartesia recommendation
- Existing Arbiter research: `.planning/research/PITFALLS.md` -- Latency stacking, TTS failure, persona derailment, audio echo

### Tertiary (LOW confidence)
- Persona prompt design is based on best practices from LLM application development but the specific Arbiter persona prompt needs iterative testing with real demo content. The example prompts in this research are starting points, not final.
- Cartesia emotion mapping to commentary content (which emotion for which type of remark) needs experimentation during development.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries verified via Context7/PyPI. Cartesia 3.0.0, google-genai already in use, FastAPI well-documented. Only new dependencies are cartesia, fastapi, uvicorn, jinja2.
- Architecture: HIGH -- Streaming LLM -> sentence buffer -> parallel TTS + display is a well-established pattern. Event bus integration follows Phases 1-2 patterns exactly. The `observation_verified` event is already published by Phase 2.
- Pitfalls: HIGH -- Latency stacking, audio echo, persona drift, TTS pronunciation are all documented in prior research and have clear mitigations.
- Persona prompt: MEDIUM -- Prompt engineering is inherently iterative. The structure and boundaries are well-defined but tone calibration requires testing with real content.

**Research date:** 2026-02-15
**Valid until:** 2026-03-15 (30 days -- Cartesia SDK is new but stable, Gemini API is stable, FastAPI is mature)
