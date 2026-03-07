# AV Input & Hosting Research — 2026-03-07

Research into how Arbiter receives audio/video from Zoom-based hackathon demos, and how to host the judging criteria reference pages.

---

## Part 1: Hosting Criteria Pages

### Context

Two standalone HTML files (`public/judge-criteria.html`, `public/audience-criteria.html`) need to be accessible to judges and audience during live demos.

### Recommendation: Mount on Existing FastAPI Server

The display server (`src/commentary/display_server.py`) already mounts two `StaticFiles` directories (`/app`, `/operator`). Add a third mount for `public/`:

```python
public_dir = Path(__file__).parent / "../../public"
if public_dir.exists():
    self._app.mount(
        "/public",
        StaticFiles(directory=str(public_dir.resolve()), html=True),
        name="public-static",
    )
```

URLs:
- `http://localhost:8080/public/judge-criteria.html`
- `http://localhost:8080/public/audience-criteria.html`

**Why this wins:** Zero new infrastructure, works offline on event LAN, consistent with existing URL scheme. Every other option (GitHub Pages, Cloudflare, Netlify) adds internet dependency at a live venue.

**Caveat:** The Tailwind CDN link in both HTML files requires internet. If venue WiFi is unreliable, self-host the CSS by inlining a minimal stylesheet.

### Options Evaluated

| Option | Setup | Reliability | Notes |
|--------|-------|-------------|-------|
| FastAPI static mount | 5 min, 4 lines | Very high (local) | Already proven pattern in codebase |
| GitHub Pages | 3 min UI setup | Needs internet | No existing Pages config |
| Cloudflare Pages | 15+ min | Needs internet | No existing wrangler config |
| Embed in React apps | Hours | High | Wrong abstraction, high effort |
| Local file open | 0 min | N/A | Poor UX for multi-device judge panel |
| Netlify/Vercel drop | 2 min | Needs internet | External service account |

---

## Part 2: AV Input for Live Judging

### Existing Codebase State

The capture layer is fully implemented at `src/capture/`:

- `audio.py` — PyAudio-based mic capture, 16kHz/16-bit PCM mono, 512-sample chunks (~32ms), mute/unmute for TTS feedback prevention
- `camera.py` — OpenCV camera capture at 1 FPS, JPEG-encoded, key frame detection via pixel diff
- `gemini_session.py` — Gemini 2.5 Flash Live API WebSocket, consumes `audio/pcm` and `image/jpeg` MediaChunk objects from a shared asyncio.Queue, session resumption with exponential backoff
- `pipeline.py` — Orchestrates all three as asyncio tasks, wired to the EventBus
- `config.py` — `AUDIO_DEVICE_INDEX` and `CAMERA_DEVICE_INDEX` are both configurable via env vars

The pipeline is parameterized by device index. Pointing it at a different audio source is a one-line `.env` change.

### Recommendation: Virtual Audio Loopback (BlackHole + OBS Virtual Camera)

Run Zoom normally on the operator's Mac. Route audio through BlackHole into the existing PyAudio pipeline. Capture video via OBS Virtual Camera.

**Setup steps:**
1. `brew install blackhole-2ch`
2. Audio MIDI Setup: create Multi-Output Device (speakers + BlackHole 2ch)
3. System Preferences > Sound > Output: set to Multi-Output Device
4. Enumerate devices: `pyaudio.PyAudio().get_device_info_by_index(N)` to find BlackHole's input index
5. `.env`: `AUDIO_DEVICE_INDEX=N`
6. Install OBS, enable Virtual Camera, add Zoom as Window Capture source
7. `.env`: `CAMERA_DEVICE_INDEX=M` (OBS Virtual Camera index)
8. Done — existing `CapturePipeline` works unchanged

**Zero code changes required.**

### Fallback: Recall.ai Bot

If physical setup is unreliable (noisy venue, operator machine far from speakers, multiple simultaneous Zoom calls):

- Recall.ai is a managed SaaS bot API — POST to join a Zoom meeting, receive real-time audio via WebSocket
- Requires writing a `RecallCapture` bridge class (~150 lines) that converts their audio to `MediaChunk` and puts it on the existing queue
- Cost is per bot-minute
- Sub-second latency claimed

### All Approaches Evaluated

| Approach | Complexity | Latency | Reliability | Audio | Video | Cost |
|----------|-----------|---------|-------------|-------|-------|------|
| BlackHole + OBS/mss | Very Low | ~0ms | Very High | Excellent | Excellent | Free |
| Recall.ai bot | Medium | <1s | High | Excellent | Good | $$/hr |
| py-zoom-meeting-sdk | Very High | Low | Low (immature) | Good | Partial | Free |
| Zoom RTMP | High | 2-5s | Medium | Good | Good | Zoom Pro |
| Recall + local video | High | Low | Medium | Excellent | Excellent | $$/hr |

### Disqualified

- **RTMP streaming** — 2-5 second inherent buffering makes live commentary react to stale information
- **py-zoom-meeting-sdk** — Linux-only, covers 36/235 SDK objects, immature

### Audio-Only vs Audio+Video

Video is needed. The Gemini session system prompt instructs it to "describe what you see on screen (slides, code, demos, terminal output)." The architecture is already correct:
- **Gemini Live API** handles real-time streaming audio + image frames
- **Claude** handles discrete key frame analysis in the scoring/deliberation layer (not a streaming consumer)
- **OpenAI Realtime API** is audio-only (no video input in streaming mode)

---

## Next Steps

1. Mount `public/` on the FastAPI server (~4 lines in `display_server.py`)
2. Document BlackHole + OBS setup procedure in `docs/pre-event-checklist.md`
3. Consider writing an `mss`-based `ScreenCapture` class (avoids OBS dependency)
4. If Recall.ai fallback is desired, build and test `RecallCapture` bridge before event day

## Sources

- [BlackHole macOS virtual audio driver](https://github.com/ExistentialAudio/BlackHole)
- [Recall.ai Zoom Bot API](https://www.recall.ai/product/meeting-bot-api/zoom)
- [Recall.ai real-time streaming docs](https://docs.recall.ai/docs/stream-media)
- [py-zoom-meeting-sdk](https://github.com/noah-duncan/py-zoom-meeting-sdk)
- [Gemini Live API overview](https://ai.google.dev/gemini-api/docs/live)
- [Zoom Meeting SDK documentation](https://developers.zoom.us/docs/meeting-sdk/)
