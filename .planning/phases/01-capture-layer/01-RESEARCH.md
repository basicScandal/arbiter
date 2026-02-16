# Phase 1: Capture Layer - Research

**Researched:** 2026-02-15
**Domain:** Real-time camera + audio capture, video frame extraction, demo lifecycle management
**Confidence:** MEDIUM-HIGH

## Summary

Phase 1 builds the foundation that every downstream component depends on: capturing live camera frames and presenter audio with clear per-team start/stop boundaries. The core technical challenge is streaming video frames and audio to the Gemini Live API via WebSocket while managing session duration limits (2 minutes for video without compression) and maintaining real-time processing throughput.

The recommended approach uses OpenCV for camera frame capture (JPEG-encoded, thumbnailed to 1024x1024), PyAudio for microphone PCM capture (16-bit, 16kHz, mono), and the google-genai SDK's `AsyncSession.send_realtime_input()` to stream both to Gemini 2.5 Flash via the Live API. Context window compression with sliding window MUST be enabled from day one to support 3-5 minute demo sessions. A Python asyncio state machine manages the demo lifecycle (idle -> capturing -> processing -> ready), and an asyncio-native event bus decouples capture from downstream consumers.

Key frame extraction does NOT require a separate library. Gemini processes video at 1 FPS natively -- the capture layer sends frames at ~1 FPS and Gemini handles the visual understanding internally. For downstream use (Phase 2+ defense layer, scoring), the capture layer stores periodic JPEG snapshots alongside the Gemini session's structured output. Simple histogram-based scene change detection (OpenCV `cv2.compareHist`) can flag slide transitions for archival without adding latency to the main pipeline.

**Primary recommendation:** Build the capture layer as three parallel asyncio tasks (frame capture, audio capture, Gemini session management) coordinated by a demo state machine, with context window compression and session resumption enabled from the start.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | ~1.63.0 | Gemini Live API client -- WebSocket streaming for video+audio input, text output | Official Google Gen AI SDK. `client.aio.live.connect()` provides async WebSocket session. `send_realtime_input(media=...)` for video, `send_realtime_input(audio=...)` for audio. HIGH confidence (Context7 verified) |
| opencv-python | ~4.13.0 | Camera frame capture and JPEG encoding | `cv2.VideoCapture(0)` for USB camera. `cap.read()` returns numpy frames. `cv2.imencode('.jpg', frame)` for JPEG. Industry standard, 2500+ fps processing. HIGH confidence (Context7 verified) |
| PyAudio | 0.2.14 | Microphone audio capture as PCM stream | Provides PortAudio bindings for Python. Captures raw 16-bit PCM at 16kHz mono -- exactly what Gemini Live API expects. HIGH confidence |
| python-statemachine | ~2.5.0 | Demo lifecycle state machine with async support | Native asyncio support. Define states as class attributes, transitions as methods. Entry/exit actions, guard conditions. Cleaner than hand-rolled enum+if chains. MEDIUM-HIGH confidence |
| Pydantic | ~2.12.5 | Data models for capture events, demo metadata, configuration | Type-safe event payloads, configuration validation. Already in stack for downstream phases. HIGH confidence |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pillow (PIL) | latest | Image resizing/thumbnailing before sending to Gemini | Thumbnail frames to 1024x1024 before JPEG encoding per Google's official example pattern |
| numpy | latest | Frame array manipulation between OpenCV and PIL | Intermediate format for frame processing. Implicit dependency of OpenCV |
| asyncio-signal-bus | latest | Lightweight async event bus for component decoupling | Pub/sub between capture, state machine, and future downstream consumers. Alternative: hand-roll with asyncio.Queue |
| python-dotenv | latest | Environment configuration | API keys, camera device index, audio device selection |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyAudio | sounddevice | sounddevice has a cleaner API but PyAudio is more widely documented with Gemini examples. PyAudio is used in Google's official Live API quickstart |
| python-statemachine | transitions (pytransitions) | transitions has AsyncMachine but python-statemachine has cleaner async-native design. Either works |
| asyncio-signal-bus | aiopubsub | aiopubsub is more mature but heavier. For this use case, even a simple dict of asyncio.Queue per event type suffices |
| OpenCV VideoCapture | ffmpeg subprocess pipe | ffmpeg is more flexible for exotic formats but adds subprocess management complexity. OpenCV is simpler for single USB camera |
| Pillow thumbnailing | OpenCV cv2.resize | Either works. Pillow is used in Google's official example. OpenCV resize is faster but the difference is negligible at 1 FPS |

**Installation:**
```bash
# System dependencies (macOS)
brew install portaudio

# Core capture layer
uv pip install google-genai~=1.63 opencv-python~=4.13 pyaudio~=0.2.14 python-statemachine~=2.5 pydantic~=2.12 pillow numpy python-dotenv
```

## Architecture Patterns

### Recommended Project Structure

```
src/
├── capture/                 # Phase 1: Capture Layer
│   ├── __init__.py
│   ├── camera.py            # OpenCV frame capture (async wrapper)
│   ├── audio.py             # PyAudio microphone capture (async wrapper)
│   ├── gemini_session.py    # Gemini Live API session management
│   ├── key_frames.py        # Scene change detection + frame archival
│   ├── demo_machine.py      # Demo lifecycle state machine
│   ├── event_bus.py         # Async pub/sub for capture events
│   ├── models.py            # Pydantic models for events/config
│   └── config.py            # Capture configuration (devices, rates, thresholds)
├── operator/                # Operator controls (start/stop/pause)
│   ├── __init__.py
│   └── cli.py               # Simple CLI or FastAPI endpoint for operator
└── main.py                  # Entry point, wires capture + operator
```

### Pattern 1: Parallel Async Task Pipeline

**What:** Three concurrent asyncio tasks share an output queue. Frame capture and audio capture run independently, pushing media chunks to a shared queue. A Gemini session task consumes from the queue and sends to the Live API.

**When to use:** Real-time streaming where camera and microphone operate at different rates and neither should block the other.

**Example:**
```python
# Source: Google's official Live API quickstart (Get_started_LiveAPI.py)
import asyncio
import base64
import io
import cv2
import PIL.Image
import pyaudio
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

CONFIG = types.LiveConnectConfig(
    response_modalities=["TEXT"],
    system_instruction="You are observing a live hackathon demo. Describe what you see and hear.",
    input_audio_transcription=types.AudioTranscriptionConfig(),
    context_window_compression=types.ContextWindowCompressionConfig(
        trigger_tokens=25600,
        sliding_window=types.SlidingWindow(target_tokens=12800),
    ),
    session_resumption=types.SessionResumptionConfig(handle=None),
)

class CaptureSession:
    def __init__(self):
        self.out_queue = asyncio.Queue(maxsize=5)
        self.session = None

    def _capture_frame(self, cap):
        ret, frame = cap.read()
        if not ret:
            return None
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)
        img.thumbnail([1024, 1024])
        buf = io.BytesIO()
        img.save(buf, format="jpeg")
        buf.seek(0)
        return {
            "mime_type": "image/jpeg",
            "data": base64.b64encode(buf.read()).decode(),
        }

    async def capture_frames(self):
        cap = await asyncio.to_thread(cv2.VideoCapture, 0)
        try:
            while True:
                frame = await asyncio.to_thread(self._capture_frame, cap)
                if frame is None:
                    break
                await self.out_queue.put(frame)
                await asyncio.sleep(1.0)  # ~1 FPS to match Gemini's processing rate
        finally:
            cap.release()

    async def capture_audio(self):
        pya = pyaudio.PyAudio()
        stream = await asyncio.to_thread(
            pya.open, format=pyaudio.paInt16, channels=1,
            rate=16000, input=True, frames_per_buffer=512
        )
        try:
            while True:
                data = await asyncio.to_thread(stream.read, 512)
                msg = {"data": data, "mime_type": "audio/pcm"}
                await self.out_queue.put(msg)
        finally:
            stream.close()
            pya.terminate()

    async def send_to_gemini(self):
        while True:
            msg = await self.out_queue.get()
            if msg["mime_type"].startswith("audio/"):
                await self.session.send_realtime_input(
                    audio=types.Blob(data=msg["data"], mime_type=msg["mime_type"])
                )
            else:
                await self.session.send_realtime_input(media=msg)

    async def receive_responses(self):
        while True:
            turn = self.session.receive()
            async for response in turn:
                if response.text:
                    print(response.text, end="")
                if sc := response.server_content:
                    if sc.input_transcription:
                        print(f"[TRANSCRIPT] {sc.input_transcription.text}")

    async def run(self):
        async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
            self.session = session
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self.capture_frames())
                tg.create_task(self.capture_audio())
                tg.create_task(self.send_to_gemini())
                tg.create_task(self.receive_responses())
```

### Pattern 2: Demo Lifecycle State Machine

**What:** An async state machine that tracks demo lifecycle: idle -> capturing -> stopped. Operator triggers transitions. State changes emit events to the event bus.

**When to use:** When multiple components need to react to demo lifecycle changes (capture start/stop, Gemini session connect/disconnect, frame archival begin/end).

**Example:**
```python
# Source: python-statemachine docs (async support)
from statemachine import StateMachine, State

class DemoMachine(StateMachine):
    idle = State(initial=True)
    capturing = State()
    stopped = State()

    start_demo = idle.to(capturing)
    stop_demo = capturing.to(stopped)
    reset = stopped.to(idle)

    async def on_enter_capturing(self, team_name: str, **kwargs):
        """Called when a demo capture begins."""
        # Start Gemini session, begin frame/audio capture
        pass

    async def on_exit_capturing(self, **kwargs):
        """Called when a demo capture ends."""
        # Stop capture, close Gemini session, archive frames
        pass

    async def on_enter_stopped(self, **kwargs):
        """Called when demo stops -- data is ready for downstream."""
        # Emit demo_complete event with captured data
        pass
```

### Pattern 3: Key Frame Detection via Histogram Comparison

**What:** Compare consecutive frame histograms to detect significant visual changes (slide transitions, switching from slides to terminal, etc.). Archive frames that differ significantly.

**When to use:** For extracting representative frames without sending every frame to an LLM.

**Example:**
```python
# Source: OpenCV docs (histogram comparison)
import cv2

def is_key_frame(prev_frame, curr_frame, threshold=0.4):
    """Detect if current frame is significantly different from previous."""
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

    prev_hist = cv2.calcHist([prev_gray], [0], None, [256], [0, 256])
    curr_hist = cv2.calcHist([curr_gray], [0], None, [256], [0, 256])

    cv2.normalize(prev_hist, prev_hist)
    cv2.normalize(curr_hist, curr_hist)

    # Correlation: 1.0 = identical, lower = more different
    score = cv2.compareHist(prev_hist, curr_hist, cv2.HISTCMP_CORREL)
    return score < threshold  # True if frames are sufficiently different
```

### Anti-Patterns to Avoid

- **Synchronous capture loop:** Never block the asyncio event loop with `cap.read()` or `stream.read()` directly. Always use `asyncio.to_thread()` to wrap blocking I/O from OpenCV and PyAudio.
- **Sending every frame to Gemini:** Gemini processes at 1 FPS. Sending 30 FPS wastes bandwidth and fills the context window 30x faster. Capture at native rate for key frame detection, but only send ~1 frame per second to Gemini.
- **No session resumption:** A 10-minute connection limit WILL hit during extended use. Without session resumption, the entire session state is lost on reconnect.
- **Coupling capture to processing:** The capture layer should produce events/data that downstream consumers subscribe to. Never import defense or scoring modules from capture code.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State machine | Enum + if/elif chains | python-statemachine | Entry/exit actions, guard conditions, transition validation, async support. Hand-rolled machines miss edge cases (re-entrant transitions, invalid state) |
| Audio capture | Raw PortAudio ctypes bindings | PyAudio | PyAudio wraps PortAudio correctly for all platforms. Raw bindings are error-prone for buffer management |
| Video frame sending to Gemini | Raw WebSocket messages | google-genai SDK `send_realtime_input()` | SDK handles message framing, reconnection, base64 encoding details. Raw WebSocket misses protocol nuances |
| Scene change detection | Custom ML model for slide detection | OpenCV histogram comparison | `cv2.compareHist` runs in <1ms per frame pair. A custom model adds inference latency and training data requirements for zero benefit at 1 FPS |
| Event bus (if complex) | Thread-based pub/sub | asyncio.Queue per event type or asyncio-signal-bus | Must be async-native. Thread-based pub/sub creates race conditions in asyncio code |

**Key insight:** Phase 1 is plumbing, not intelligence. Every component has a well-established library solution. The engineering challenge is async orchestration, not algorithm design.

## Common Pitfalls

### Pitfall 1: Gemini Session Dies at 2 Minutes (Video)

**What goes wrong:** Without context window compression, audio+video sessions terminate at exactly 2 minutes. Video consumes 258 tokens/second; at 128k context window, that is ~8.3 minutes of pure video, but with audio (25 TPS) and model output tokens, the real limit is ~2 minutes.
**Why it happens:** Compression is not enabled by default. Developers test with short clips and never hit the limit until a real 3-5 minute demo.
**How to avoid:** Enable `ContextWindowCompressionConfig` with `sliding_window` in the `LiveConnectConfig` from the very first session. Set `trigger_tokens=25600` and `target_tokens=12800` (per Google's official example). Test with a 5-minute continuous session as an acceptance criterion.
**Warning signs:** No compression config in session setup. Tests only run for 30-60 seconds.

### Pitfall 2: WebSocket Connection Drops at ~10 Minutes

**What goes wrong:** Even with compression extending the session indefinitely, the underlying WebSocket connection has a ~10 minute lifetime. The connection drops and all session state is lost.
**Why it happens:** This is a server-side limit on WebSocket connections, separate from the context window limit.
**How to avoid:** Enable `SessionResumptionConfig` in `LiveConnectConfig`. Store the latest `new_handle` from `SessionResumptionUpdate` messages. On disconnect, reconnect with the stored handle. Listen for `GoAway` messages to proactively reconnect before forced termination. Resumption tokens are valid for 2 hours.
**Warning signs:** No session resumption config. No GoAway message handling. Session handle not persisted.

### Pitfall 3: Blocking the asyncio Event Loop

**What goes wrong:** `cv2.VideoCapture.read()` and `pyaudio.Stream.read()` are blocking calls. Calling them directly in async code freezes the entire event loop -- no other coroutine runs until the blocking call returns.
**Why it happens:** OpenCV and PyAudio are C libraries with no native async support. Developers accustomed to Node.js expect I/O to be non-blocking by default.
**How to avoid:** Always wrap blocking calls with `await asyncio.to_thread()`. This runs them in a thread pool without blocking the event loop. Google's official example uses this pattern: `frame = await asyncio.to_thread(self._capture_frame, cap)`.
**Warning signs:** Direct `cap.read()` calls inside `async def` functions. Audio capture without `to_thread()`.

### Pitfall 4: Audio Echo -- Capturing Arbiter's Own Voice

**What goes wrong:** When Arbiter speaks through venue speakers (later phases), the microphone picks up Arbiter's own TTS output and transcribes it as presenter speech, creating a feedback loop.
**Why it happens:** Microphone and speakers are in the same room. No acoustic echo cancellation in the default pipeline.
**How to avoid:** Design the audio capture state machine from the start with a `muted` state. When downstream TTS is playing (Phase 3+), mute microphone input. Use a state enum: `LISTENING -> PROCESSING -> SPEAKING -> LISTENING`. For Phase 1, expose a `mute()`/`unmute()` API on the audio capture module so Phase 3 can control it. Also: use a directional microphone pointed at the presenter, not a room mic.
**Warning signs:** No mute/unmute capability in audio capture API. Omnidirectional microphone in hardware plan.

### Pitfall 5: Queue Backpressure -- Frames Pile Up

**What goes wrong:** Camera captures frames faster than Gemini can process them. The output queue grows unbounded. Memory usage climbs. Eventually the system becomes unresponsive.
**Why it happens:** Camera runs at 30 FPS natively, but we only need ~1 FPS for Gemini. If the sleep interval is wrong or Gemini is slow, frames accumulate.
**How to avoid:** Use `asyncio.Queue(maxsize=5)` (per Google's official example). When the queue is full, the producer blocks (or drop the oldest frame). Capture at ~1 FPS with `await asyncio.sleep(1.0)` between captures. For key frame detection, capture at higher rate but only enqueue frames that pass the histogram threshold.
**Warning signs:** Unbounded queue (`asyncio.Queue()` with no maxsize). No sleep between frame captures.

## Code Examples

### Complete Gemini Live API Session Setup

```python
# Source: Google official quickstart + Live API docs (verified via Context7)
import os
from google import genai
from google.genai import types

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options={"api_version": "v1beta"},
)

MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

config = types.LiveConnectConfig(
    # TEXT output for Phase 1 (no TTS yet)
    response_modalities=["TEXT"],

    # System instruction for the observation/extraction role
    system_instruction=(
        "You are observing a live hackathon demo presentation. "
        "Describe what you see on screen (slides, code, terminal output) "
        "and what the presenter is saying. Output structured observations."
    ),

    # Enable audio input transcription (gives us text transcript)
    input_audio_transcription=types.AudioTranscriptionConfig(),

    # CRITICAL: Enable compression for 3-5 min sessions
    context_window_compression=types.ContextWindowCompressionConfig(
        trigger_tokens=25600,
        sliding_window=types.SlidingWindow(target_tokens=12800),
    ),

    # CRITICAL: Enable session resumption for >10 min connections
    session_resumption=types.SessionResumptionConfig(handle=None),
)

async def connect():
    async with client.aio.live.connect(model=MODEL, config=config) as session:
        # session.send_realtime_input(media=...) for video
        # session.send_realtime_input(audio=...) for audio
        # session.receive() for responses
        pass
```

### Camera Frame Capture and Encoding

```python
# Source: OpenCV docs (Context7) + Google Live API quickstart
import asyncio
import base64
import io
import cv2
import PIL.Image

async def capture_frames(queue: asyncio.Queue, stop_event: asyncio.Event):
    """Capture camera frames at ~1 FPS, encode as JPEG, push to queue."""
    cap = await asyncio.to_thread(cv2.VideoCapture, 0)
    if not cap.isOpened():
        raise RuntimeError("Cannot open camera")

    try:
        while not stop_event.is_set():
            ret, frame = await asyncio.to_thread(cap.read)
            if not ret:
                break

            # Convert BGR -> RGB, thumbnail to 1024x1024
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = PIL.Image.fromarray(frame_rgb)
            img.thumbnail([1024, 1024])

            # Encode as JPEG
            buf = io.BytesIO()
            img.save(buf, format="jpeg")
            buf.seek(0)

            msg = {
                "mime_type": "image/jpeg",
                "data": base64.b64encode(buf.read()).decode(),
            }

            # Non-blocking put with bounded queue
            try:
                queue.put_nowait(msg)
            except asyncio.QueueFull:
                pass  # Drop frame if queue full

            await asyncio.sleep(1.0)  # ~1 FPS
    finally:
        cap.release()
```

### Audio Capture as PCM Stream

```python
# Source: Google Live API quickstart + PyAudio docs
import asyncio
import pyaudio

AUDIO_FORMAT = pyaudio.paInt16
CHANNELS = 1
SAMPLE_RATE = 16000
CHUNK_SIZE = 512  # ~32ms chunks at 16kHz

async def capture_audio(queue: asyncio.Queue, stop_event: asyncio.Event):
    """Capture microphone audio as 16-bit PCM, 16kHz mono."""
    pya = pyaudio.PyAudio()
    stream = await asyncio.to_thread(
        pya.open,
        format=AUDIO_FORMAT,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK_SIZE,
    )

    try:
        while not stop_event.is_set():
            data = await asyncio.to_thread(stream.read, CHUNK_SIZE)
            msg = {"data": data, "mime_type": "audio/pcm"}
            try:
                queue.put_nowait(msg)
            except asyncio.QueueFull:
                pass  # Drop oldest audio chunk if queue full
    finally:
        stream.close()
        pya.terminate()
```

### Session Resumption Handler

```python
# Source: Gemini Live API session management docs (Context7 verified)
async def receive_with_resumption(session, handle_store: dict):
    """Receive responses and track session resumption handles."""
    async for message in session.receive():
        # Track resumption handle for reconnection
        if message.session_resumption_update:
            update = message.session_resumption_update
            if update.resumable and update.new_handle:
                handle_store["handle"] = update.new_handle

        # Process text responses
        if message.text:
            yield {"type": "observation", "text": message.text}

        # Process input transcription
        if (sc := message.server_content) and sc.input_transcription:
            yield {"type": "transcript", "text": sc.input_transcription.text}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate STT pipeline (Whisper/Deepgram) + separate vision API | Gemini Live API handles audio + video natively in one WebSocket | 2025 (Gemini 2.0 Live API GA) | Eliminates STT integration, reduces latency by ~1-3s, single session handles both modalities |
| Manual frame sampling + polling LLM API | Live API processes video at 1 FPS natively via streaming | 2025 | No need to manage frame rate sampling logic; API handles timing |
| Context window overflow = session death | Sliding window compression extends sessions indefinitely | 2025 | 3-5 min demos are feasible without session restarts |
| Connection drops = lost state | Session resumption with 2-hour token validity | 2025 | Graceful recovery from network blips without losing demo context |

**Deprecated/outdated:**
- Whisper for live STT in the capture pipeline: Not needed when using Gemini Live API with `input_audio_transcription`. Still useful as backup transcript logger (Deepgram) but not in the critical path
- Manual frame-rate management for LLM vision: Gemini's 1 FPS native processing makes client-side frame rate management unnecessary beyond basic throttling

## Open Questions

1. **TEXT response modality with video input on Live API**
   - What we know: The Live API supports `response_modalities=["TEXT"]` and accepts video via `send_realtime_input(media=...)`. Google's quickstart uses AUDIO modality with video input.
   - What's unclear: Whether TEXT response mode works correctly with video input on all Live API models, or if the native-audio models require AUDIO output. The docs say "You can only set one response modality (TEXT or AUDIO) per session."
   - Recommendation: Test TEXT mode with video input early in Phase 1. If TEXT+video is not supported, use AUDIO mode and add `output_audio_transcription` to get text. Fallback: use `gemini-2.5-flash` (non-native-audio) if it supports Live API.

2. **Optimal compression token thresholds for 3-5 min demos**
   - What we know: Google's example uses `trigger_tokens=25600, target_tokens=12800`. Video is 258 TPS, audio is 25 TPS. A 5-min demo = ~85,000 video tokens + ~7,500 audio tokens.
   - What's unclear: Whether the default thresholds cause premature context loss (losing early demo content before demo ends). The sliding window discards oldest turns first.
   - Recommendation: Test with higher thresholds (trigger=80000, target=60000) to retain more demo content. Measure quality of observations at minute 4-5 vs minute 1 to detect context degradation.

3. **Camera device selection at venue**
   - What we know: `cv2.VideoCapture(0)` opens the default camera. USB webcams get assigned device indices.
   - What's unclear: What camera will be available at the venue. Resolution, angle, and lighting conditions are unknown.
   - Recommendation: Make device index configurable via environment variable. Support resolution override. Test with both laptop webcam and external USB camera. Plan to arrive 2+ hours early at venue for camera positioning.

4. **Audio device selection and noise in venue**
   - What we know: PyAudio can enumerate input devices. Venue will have ambient noise from 200+ attendees.
   - What's unclear: Whether the venue provides a dedicated audio feed from the presenter mic, or if we capture room audio.
   - Recommendation: Make audio device configurable. Strongly prefer a direct audio feed from the venue's audio board (3.5mm line-in or USB audio interface) over a room microphone. Design audio capture to support device selection by index or name.

## Sources

### Primary (HIGH confidence)
- Context7: `/googleapis/python-genai` -- LiveConnectConfig, AsyncSession methods, send_realtime_input API
- Context7: `/websites/ai_google_dev_gemini-api` -- Session management, compression, resumption, token rates
- Context7: `/websites/opencv_4_x` -- VideoCapture, frame read, video display tutorial
- [Google Official Live API Quickstart](https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_LiveAPI.py) -- Complete Python example with camera+audio capture pattern
- [Gemini Live API Session Management](https://ai.google.dev/gemini-api/docs/live-session) -- Session lifetime (2 min video, 15 min audio), compression config, resumption
- [Gemini Live API Capabilities Guide](https://ai.google.dev/gemini-api/docs/live-guide) -- Audio format (16-bit PCM 16kHz), VAD config, send_realtime_input
- [Firebase Live API Limits](https://firebase.google.com/docs/ai-logic/live-api/limits-and-specs) -- Video at 768x768 native, 1 FPS, connection ~10 min

### Secondary (MEDIUM confidence)
- [python-statemachine async docs](https://python-statemachine.readthedocs.io/en/latest/async.html) -- AsyncEngine, activate_initial_state
- [SAGE-Rebirth/gemini-live](https://github.com/SAGE-Rebirth/gemini-live) -- Community example of camera+audio streaming to Gemini Live API
- [Vertex AI Live API Reference](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/multimodal-live) -- BidiGenerateContentRealtimeInput message format, media_chunks structure
- [OpenCV histogram comparison](https://docs.opencv.org/3.4/d8/dc8/tutorial_histogram_comparison.html) -- cv2.compareHist for scene change detection

### Tertiary (LOW confidence, needs validation)
- Token consumption rate of 258 TPS for video and 25 TPS for audio -- cited in multiple sources but exact behavior under compression needs hands-on validation
- TEXT response modality compatibility with video input -- documentation is ambiguous, needs testing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries verified via Context7 and official docs. Versions confirmed on PyPI. Google's official quickstart uses exact same pattern (OpenCV + PyAudio + google-genai)
- Architecture: MEDIUM-HIGH -- Parallel asyncio tasks pattern is proven (Google's official example). State machine integration is standard but untested with this specific stack combination
- Pitfalls: HIGH -- Session limits (2 min, 10 min) verified in official docs. Compression and resumption configs verified via Context7. Echo cancellation is a known domain problem
- Key frame extraction: MEDIUM -- Histogram comparison is well-established but threshold tuning needs per-venue calibration

**Research date:** 2026-02-15
**Valid until:** 2026-03-15 (30 days -- Gemini API is evolving rapidly, check for model name changes)
