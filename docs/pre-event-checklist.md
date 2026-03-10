# Pre-Event Checklist -- NEBULA:FOG 2026

## Hardware

- [ ] Camera connected and pointed at demo screen
- [ ] Microphone connected for presenter audio
- [ ] Projector/screen for audience display (separate browser, full-screen)
- [ ] Operator laptop with dashboard (separate from audience display)
- [ ] All devices on same network

## Software

- [ ] Python 3.11+ installed
- [ ] `uv sync` completed (all dependencies installed)
- [ ] Tesseract OCR installed (`brew install tesseract` / `apt install tesseract-ocr`)
- [ ] Frontend builds current:
  ```bash
  cd operator-dashboard && bun install && bun run build
  cd audience-display && bun install && bun run build
  ```

## API Keys

- [ ] `GEMINI_API_KEY` set and valid
- [ ] `ANTHROPIC_API_KEY` set and valid (Claude fallback)
- [ ] `CARTESIA_API_KEY` set and valid (TTS)
- [ ] `OPENAI_API_KEY` set (TTS fallback)
- [ ] `GROQ_API_KEY` set (commentary fallback)

## Device Configuration

- [ ] `CAMERA_DEVICE_INDEX` set to correct camera
- [ ] `AUDIO_DEVICE_INDEX` set to correct microphone
- [ ] Test camera capture manually if possible

### Zoom-Based Demos (see [zoom-capture-setup.md](zoom-capture-setup.md))

- [ ] BlackHole installed and Multi-Output Device configured
- [ ] OBS running with Virtual Camera started
- [ ] Verify device indices with discovery script

## Verification

- [ ] Start server: `uv run arbiter`
- [ ] Operator dashboard loads: http://localhost:8080/operator/
- [ ] Audience display loads: http://localhost:8080/app/
- [ ] Both show green connection dot
- [ ] Health endpoint returns OK: `curl http://localhost:8080/api/health`
- [ ] Run smoke tests: `uv run pytest -m smoke`
- [ ] Run one rehearsal demo from dashboard to verify full pipeline
- [ ] Verify TTS audio plays (check speakers/PA system)
- [ ] Verify audience display is visible on projector

## Edge Case Verification

- [ ] Timer shows `--:--` when idle, green elapsed time when capturing
- [ ] Buttons show spinning indicator while command is pending
- [ ] Kill network briefly, confirm: reconnect banner appears, dashboard resyncs state
- [ ] Audience display also resyncs after network drop
- [ ] Connection banner shows "CONNECTING..." on initial load (before first connect)
- [ ] Long team name (30+ chars) truncates cleanly on audience display
- [ ] If server is down, clicking a button shows "Not connected" error immediately

## Day-of

- [ ] `data/` directory exists and is writable
- [ ] Previous demo data cleared if starting fresh
- [ ] `OPERATOR_TOKEN` set if using authentication
- [ ] Audience display browser in full-screen mode (F11)
- [ ] Backup plan: human scoring API if LLMs fail
