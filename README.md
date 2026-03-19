# Arbiter

[![CI](https://github.com/basicScandal/arbiter/actions/workflows/ci.yml/badge.svg)](https://github.com/basicScandal/arbiter/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-1451%20passed-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Event](https://img.shields.io/badge/NEBULA%3AFOG-2026-cyan)](https://nebulafog.ai)
[![Featured on Starlog](https://starlog.is/api/badge/cybersecurity/basicscandal-arbiter.svg)](https://starlog.is/api/badge-click/cybersecurity/basicscandal-arbiter)

**Live AI judge agent for hackathons.** Watches demos in real-time via camera and microphone, delivers entertainment commentary with a British accent, scores projects against a rubric using a multi-model ensemble, detects prompt injection attempts, and runs cross-team deliberation with full memory of every demo.

Built for the [NEBULA:FOG 2026](https://nebulafog.ai) security hackathon, where it judged 25 live demos on March 14, 2026.

> *"Twenty-five teams walked in with 24 hours of code and a live demo slot. What they didn't expect: an AI judge watching every second."*

## What It Does

- **Real-time observation** — Connects to Gemini Live API, streams audio/video, generates observations as presenters speak
- **Multi-layer injection defense** — Regex denylist, semantic classifier (rubric echo, self-eval, fabricated evidence), multi-language detection (7 languages), XML boundary tags, dual-LLM privilege separation
- **AI commentary** — Generates sharp, persona-driven reviews delivered via Cartesia TTS (British voice)
- **Multi-model scoring** — Gemini, Claude, and Groq independently score each demo, aggregated with outlier detection
- **Theatrical score reveal** — Animated criterion-by-criterion reveal on the audience display
- **Q&A generation** — Generates pointed follow-up questions based on what was actually said in the demo
- **Cross-team deliberation** — After all demos, compares every team against every other team for final rankings
- **Operator dashboard** — React WebSocket control panel for managing demo lifecycle
- **Audience display** — React real-time display for commentary, scores, and leaderboard

## Architecture

```
Capture Layer ──→ Defense Pipeline ──→ Commentary ──→ Scoring ──→ Deliberation
  (audio+video)    (injection guard)    (persona TTS)   (MoE rubric)  (memory)
```

**Dual-LLM privilege separation:** A quarantined Gemini Live session processes raw input. The privileged judging LLM only sees sanitized observations — never raw camera frames or audio.

| Module | Purpose |
|--------|---------|
| `src/capture/` | Audio capture, camera, key frame detection, Gemini Live API session |
| `src/defense/` | Regex + semantic injection detection, OCR scanning, roast generation, sanitization |
| `src/commentary/` | Streaming LLM commentary, Cartesia TTS, Q&A generation, display server |
| `src/scoring/` | Rubric-based scoring, MoE multi-model ensemble, theatrical score reveal |
| `src/memory/` | Per-demo structured memory, deliberation engine, rankings |
| `src/operator/` | WebSocket operator dashboard for demo lifecycle management |
| `src/resilience/` | Circuit breakers, rate limiting, TTS failover, graceful degradation |
| `src/rehearsal/` | Full pipeline rehearsal with synthetic events and canned responses |
| `src/replay/` | Video analysis pipeline for scoring recorded demos offline |
| `operator-dashboard/` | React operator control panel (Vite + TypeScript) |
| `audience-display/` | React audience-facing display for commentary and scores (Vite + TypeScript) |
| `public/` | Static pages — judge criteria, audience criteria, live scoreboard |

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [bun](https://bun.sh/) (JS package manager, for frontend builds)
- A [Gemini API key](https://aistudio.google.com/apikey)

### Setup

```bash
git clone https://github.com/basicScandal/arbiter.git
cd arbiter
uv sync
cp .env.example .env
# Edit .env — at minimum set GEMINI_API_KEY
```

### Build frontends

```bash
cd operator-dashboard && bun install && bun run build && cd ..
cd audience-display && bun install && bun run build && cd ..
```

### Run

```bash
# Live mode (requires camera + microphone)
uv run python -m src.main

# Rehearsal mode (no hardware or API keys needed)
uv run python -m src.main --rehearsal
```

### URLs

| Page | URL |
|------|-----|
| Operator Dashboard | http://localhost:8080/operator/ |
| Audience Display | http://localhost:8080/app/ |
| Live Scoreboard | http://localhost:8080/public/scoreboard.html |
| Judge Criteria | http://localhost:8080/public/judge-criteria.html |
| Health Check | http://localhost:8080/api/health |

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | *required* | Google AI Studio API key |
| `CAMERA_DEVICE_INDEX` | `-1` | OpenCV camera device index (-1 for auto-detect) |
| `DISABLE_CAMERA` | `false` | Set to `true`/`1`/`yes` to skip camera capture entirely (prevents OOM on memory-constrained hosts) |
| `AUDIO_DEVICE_INDEX` | system default | PyAudio input device index |
| `FRAME_RATE` | `1.0` | Frames per second to capture |
| `CARTESIA_API_KEY` | — | Cartesia TTS API key (degrades to macOS `say` without it) |
| `CARTESIA_VOICE_ID` | — | Cartesia voice ID for the Arbiter persona |
| `ANTHROPIC_API_KEY` | — | Claude API key (MoE scoring) |
| `OPENAI_API_KEY` | — | OpenAI API key (TTS fallback) |
| `GROQ_API_KEY` | — | Groq API key (commentary and Q&A generation) |
| `MOE_SCORING_ENABLED` | `false` | Enable multi-model scoring ensemble |
| `OPERATOR_TOKEN` | — | WebSocket auth token for operator dashboard |
| `DISPLAY_TOKEN` | — | WebSocket auth token for audience display |

## Testing

```bash
# Full suite (1451 tests)
uv run pytest

# Smoke tests only (fast go/no-go gate)
uv run pytest -m smoke

# Specific module
uv run pytest tests/test_semantic_detection.py -v
```

## Security

Arbiter is designed to operate in an adversarial environment where participants actively try to hack the judge. The defense stack has four layers:

| Layer | What It Catches |
|-------|----------------|
| **Regex denylist** (11 patterns) | "ignore previous instructions", score manipulation, delimiter escapes |
| **Semantic classifier** | Rubric language echoing, self-evaluation phrases, fabricated evidence markers |
| **Multi-language detection** | Injection attempts in ES, FR, DE, ZH, JA, KO, RU |
| **Structural defenses** | Dual-LLM privilege separation, XML boundary tags, Python-side score clamping, base64 decoding, Unicode normalization (18 invisible characters) |

The system was [red-teamed post-event](docs/red-team-report.md) by three parallel AI agents that identified 11 findings (all fixed in v1.1.0). See the [full report](docs/red-team-report.md) and [slide deck](docs/red-team-slides.html).

## How Scoring Works

Each demo is scored across three criteria:

| Criterion | Weight | What's Evaluated |
|-----------|--------|-----------------|
| Technical Execution | 40% | Implementation quality, functionality, edge case handling |
| Innovation | 30% | AI x Security novelty, creative approaches |
| Demo Quality | 30% | Clarity of explanation, working live demo, compelling narrative |

Plus a **track-specific bonus** (+10%) based on the team's chosen challenge track.

Scoring uses a **Mixture of Experts (MoE)** approach: Gemini, Claude, and Groq independently evaluate each demo. Scores are aggregated with outlier detection — if one model disagrees wildly, it's flagged and its influence is reduced.

## Event Day Results

The `data/` directory contains all event outputs:

- `data/scores/` — Per-team scorecards with criterion breakdowns
- `data/observations/` — Raw observations and transcripts from each demo
- `data/deliberation/` — Cross-team comparative analysis
- `data/events.jsonl` — Complete event log
- `data/audit.jsonl` — Full audit trail

## Docs

- [How We Built Arbiter](docs/how-we-built-arbiter.md) — full writeup with architecture, what broke, and lessons learned
- [Red Team Report](docs/red-team-report.md) — 11 prompt injection findings from 3 parallel AI red team agents
- [Red Team Slides](docs/red-team-slides.html) — 10-slide HTML deck summarizing findings
- [Architecture](docs/architecture.md)
- [Operator Guide](docs/operator-guide.md)
- [Pre-Event Checklist](docs/pre-event-checklist.md)
- [Judge Instructions](docs/judge-instructions.md)
- [Prize Breakdown](docs/prize-breakdown.md)
- [Zoom Capture Setup](docs/zoom-capture-setup.md)

## See It In Action

- [SINGULARITY 2026 Results](https://nebulafog.ai/singularity-results.html) — full scoreboard with 25 teams
- [PRIME 2025 Results](https://nebulafog.ai/prime-results.html) — retroactive scoring of 15 demos from video
- [YouTube: NEBULA:FOG](https://www.youtube.com/@nebulafog) — demo recordings

## License

MIT
