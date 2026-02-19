# Arbiter

Live AI judge agent for the **NEBULA:FOG 2026** security hackathon.

Arbiter sits on the judging panel alongside human judges, watches live 3–5 minute demos via camera and microphone, delivers real-time entertainment commentary (Simon Cowell meets hacker), scores projects against official criteria, and participates in deliberation with full memory of every demo.

Built to be entertaining, fair, and — critically — resistant to prompt injection from a security-savvy audience.

## Architecture

```
Capture Layer ──→ Defense Pipeline ──→ Commentary ──→ Scoring ──→ Deliberation
  (camera+mic)     (injection guard)    (persona TTS)   (rubric)    (memory)
```

**Dual-LLM privilege separation:** A quarantined Gemini session processes raw input. The privileged judging LLM only sees sanitized observations — never raw camera frames or audio.

| Module | Purpose |
|--------|---------|
| `src/capture/` | Camera, audio, key frame detection, Gemini Live API session |
| `src/defense/` | OCR scanning, regex injection detection, roast generation, sanitization |
| `src/commentary/` | Streaming LLM commentary, Cartesia TTS, Q&A generation, display server |
| `src/scoring/` | Rubric-based scoring, MoE multi-model voting, theatrical score reveal |
| `src/memory/` | Per-demo structured memory, deliberation engine, rankings |
| `src/operator/` | Interactive CLI and React WebSocket dashboard for demo lifecycle |
| `src/resilience/` | Health checks, rate limiting, TTS failover, graceful degradation |
| `src/rehearsal/` | Full pipeline rehearsal with synthetic events and canned responses |
| `src/replay/` | Video analysis pipeline for scoring recorded demos offline |
| `operator-dashboard/` | React operator control panel (Vite + TypeScript) |
| `audience-display/` | React audience-facing display for commentary and scores (Vite + TypeScript) |

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package manager)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- A [Gemini API key](https://aistudio.google.com/apikey)

### System dependencies

```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt install tesseract-ocr
```

## Setup

```bash
git clone git@github.com:basicScandal/arbiter.git
cd arbiter
uv sync
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

## Usage

```bash
uv run arbiter
```

### Operator commands

| Command | Description |
|---------|-------------|
| `start <team>` | Begin capturing a team's demo |
| `stop` | End the current demo |
| `pause` / `resume` | Temporarily halt and resume capture |
| `reset` | Clear session, prepare for next demo |
| `qa` | Trigger Q&A questions for the current team |
| `deliberate` | Run cross-demo deliberation and rankings |
| `status` | Show current state and duration |
| `help` | List available commands |
| `quit` | Shutdown |

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | *required* | Google AI Studio API key |
| `CAMERA_DEVICE_INDEX` | `0` | OpenCV camera device index |
| `AUDIO_DEVICE_INDEX` | system default | PyAudio input device index |
| `FRAME_RATE` | `1.0` | Frames per second to capture |
| `KEY_FRAME_THRESHOLD` | `0.4` | Scene change sensitivity (lower = more sensitive) |
| `CARTESIA_API_KEY` | — | Cartesia TTS API key (optional, degrades to text-only) |
| `CARTESIA_VOICE_ID` | — | Cartesia voice ID for the Arbiter persona |
| `DISPLAY_HOST` | `0.0.0.0` | Display server bind address |
| `DISPLAY_PORT` | `8080` | Display server port |
| `ANTHROPIC_API_KEY` | — | Claude API key (MoE scoring, video analysis) |
| `OPENAI_API_KEY` | — | OpenAI API key (MoE scoring, TTS fallback) |
| `GROQ_API_KEY` | — | Groq API key (fast commentary and Q&A) |
| `MOE_SCORING_ENABLED` | `false` | Enable multi-model scoring ensemble |
| `COMMENTARY_ENRICHMENT_ENABLED` | `false` | Enable second-pass commentary polish |

## Roadmap

### v1.0 — Core Pipeline (Phases 1–6)

- [x] **Phase 1** — Capture layer (camera, audio, key frames, Gemini Live API session)
- [x] **Phase 2** — Defense pipeline (OCR, injection detection, roasting, sanitization)
- [x] **Phase 3** — Commentary and output (streaming persona TTS, Q&A, audience display)
- [x] **Phase 4** — Scoring system (rubric engine, MoE multi-model voting, theatrical reveal)
- [x] **Phase 5** — Memory and deliberation (per-demo recall, cross-demo rankings)
- [x] **Phase 6** — Venue hardening (health checks, rate limiting, TTS failover, degraded modes)

### v1.1 — Production Polish (Phases 7–10)

- [x] **Phase 7** — Operator dashboard (React WebSocket control panel)
- [x] **Phase 8** — Audience display (React real-time commentary and score reveal)
- [x] **Phase 9** — Rehearsal mode (synthetic capture, canned responses, full pipeline exercise)
- [x] **Phase 10** — Dashboard hardening (reconnection, state sync, audio feedback)

## License

Private. All rights reserved.
