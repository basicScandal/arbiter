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
| `src/operator/` | Interactive CLI for demo lifecycle control |

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
| `reset` | Clear session, prepare for next demo |
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

## Roadmap

- [x] **Phase 1** — Capture layer (camera, audio, key frames, Gemini session)
- [x] **Phase 2** — Defense pipeline (OCR, injection detection, roasting, sanitization)
- [ ] **Phase 3** — Commentary & output (persona TTS, text display)
- [ ] **Phase 4** — Scoring system (rubric: Technical 40%, Innovation 30%, Demo 30%)
- [ ] **Phase 5** — Memory & deliberation (per-demo recall, comparative analysis)
- [ ] **Phase 6** — Venue hardening (network resilience, TTS failover, degraded modes)

## License

Private. All rights reserved.
