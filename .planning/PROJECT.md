# Arbiter

## What This Is

Arbiter is a live AI judge agent for the NEBULA:FOG 2026 hackathon. It watches 3-5 minute demos via camera + audio, defends against prompt injection with dual-LLM privilege separation, delivers Simon Cowell-meets-hacker commentary via TTS, scores against the official rubric with isolated scoring pipeline, and produces comparative rankings with full demo memory for deliberation.

## Core Value

Arbiter must produce fair, defensible scores that hold up alongside human judge scores — while being entertaining and resistant to prompt injection from a security-savvy audience that will absolutely try to exploit it.

## Requirements

### Validated

- ✓ Live multimodal input processing (camera + audio from demos) — v1.0
- ✓ Post-demo commentary generation with streaming Gemini — v1.0
- ✓ TTS voice output (Cartesia + macOS say fallback) + text display for audience — v1.0
- ✓ Scoring against official NEBULA:FOG rubric (40/30/30 weights, 4 track variants) — v1.0
- ✓ Dual-LLM prompt injection defense (visual OCR + verbal scanning) — v1.0
- ✓ Injection detection with public roasting and structured logging — v1.0
- ✓ Simon Cowell-meets-hacker personality with 12-emotion TTS variety — v1.0
- ✓ Theatrical score card with CSS-animated reveals after each demo — v1.0
- ✓ Per-demo memory storage with end-of-event comparative deliberation — v1.0
- ✓ Q&A question generation from structured observations — v1.0
- ✓ Per-demo scoring notes with per-criterion breakdown and justification — v1.0

### Active

(None — v1.0 shipped. Define new requirements with `/gsd:new-milestone`)

### Out of Scope

- Real-time commentary during demos — post-demo sufficient for v1, deferred to v2
- Mobile app — venue deployment only
- Self-hosted LLM — cloud APIs provide better quality within timeline
- Automated prize distribution — Arbiter scores, humans handle logistics
- Post-event analytics dashboard — focus is live event performance
- Audience chat integration — massive injection surface, not worth the risk
- Repository/code scanning — attack surface too large, camera captures code on screen

## Context

Shipped v1.0 with 6,141 LOC Python across 113 files.
Tech stack: Python 3.12, Gemini 2.0/2.5 Flash, Cartesia TTS, OpenCV, PyAudio, FastAPI, Textual TUI.
Architecture: Event-driven async pipeline with 4 isolated Gemini clients (defense, commentary, scoring, deliberation).
Built in 2 days (2026-02-15 → 2026-02-16), 19 plans across 6 phases.

- **Event:** NEBULA:FOG 2026 hackathon, March 2026
- **Audience:** Security researchers, hackers, builders — technically sophisticated and adversarial
- **Panel:** Arbiter is one of several judges; human judges can defer Q&A to it
- **Voting power:** Equal voting member — scores count toward prize decisions
- **Demo count:** ~24 projects expected
- **Tracks:** SHADOW::VECTOR (attack), SENTINEL::MESH (defense), ZERO::PROOF (privacy), ROGUE::AGENT (novel)

## Constraints

- **Timeline:** ~2 weeks to working prototype — must be reliable for live event
- **Input method:** Physical camera + audio in venue (not screen share)
- **Latency:** Commentary and reactions must feel responsive (seconds, not minutes)
- **Reliability:** Cannot crash or go silent during a live event with audience
- **Stack:** Flexible — best tool for each capability (likely multimodal LLM for vision+audio, separate TTS)
- **Deployment:** Flexible — whatever maximizes reliability at venue

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Gemini Live API for vision+audio processing | Multimodal streaming with context window compression and session resumption | ✓ Good — handles real-time media well |
| Separate scoring from commentary generation | Injection defense requires isolated LLM clients on scoring path | ✓ Good — 4 isolated Gemini clients, SCORE-03 verified |
| Simon Willison dual-LLM pattern for injection defense | Quarantined model processes raw input, privileged model generates output | ✓ Good — SanitizedOutput is only trust boundary crossing |
| Camera + audio input (not screen share) | Physical venue setup, more natural judge experience | ✓ Good — OpenCV + PyAudio capture working |
| Independent scoring with deliberation memory | Fair per-demo scoring but enables comparative analysis at end | ✓ Good — Python-authoritative rankings, never trust LLM ordering |
| Hand-rolled async event bus | Lightweight alternative to external library, asyncio.create_task dispatch | ✓ Good — 8 publishers, 20 subscribers, 16 event types |
| Cartesia WebSocket TTS with macOS say fallback | Primary quality TTS with offline fallback chain | ✓ Good — graceful degradation verified |
| Python-computed scores (never trust LLM arithmetic) | LLM provides qualitative assessment, Python computes weighted totals | ✓ Good — eliminates score manipulation risk |
| Textual TUI over stdin CLI | Rich operator interface with keybindings and visual feedback | ✓ Good — replaced basic input() loop |
| Detached asyncio tasks for display/reveals | Score reveals and display pushes must not block event bus | ✓ Good — consistent pattern across scoring and deliberation |

---
*Last updated: 2026-02-16 after v1.0 milestone*
