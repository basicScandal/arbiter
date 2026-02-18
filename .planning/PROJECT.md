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

- ✓ E2E integration tests across full pipeline (capture → defense → commentary → scoring → deliberation) — v1.1
- ✓ Rehearsal/dry-run mode for testing without live camera — v1.1
- ✓ Groq fallback for scoring pipeline (not just commentary) — v1.1
- ✓ MoE ensemble scoring tested end-to-end with real multi-provider flow — v1.1
- ✓ Operator web dashboard hardening (reconnect, health status, live scoring) — v1.1

### Active

(None — planning next milestone)

### Out of Scope

- Real-time commentary during demos — post-demo sufficient for v1, deferred to v2
- Mobile app — venue deployment only
- Self-hosted LLM — cloud APIs provide better quality within timeline
- Automated prize distribution — Arbiter scores, humans handle logistics
- Post-event analytics dashboard — focus is live event performance
- Audience chat integration — massive injection surface, not worth the risk
- Repository/code scanning — attack surface too large, camera captures code on screen

## Context

Shipped v1.1 with ~18K LOC Python + ~2.4K LOC TypeScript.
Tech stack: Python 3.13, Gemini 2.0/2.5 Flash, Cartesia TTS, OpenCV, PyAudio, FastAPI, React + Vite + Zustand (operator dashboard), Groq (scoring fallback).
Architecture: Event-driven async pipeline with 4 isolated Gemini clients (defense, commentary, scoring, deliberation) + MoE scoring engine with timeout hardening.
Test suite: 371 parallel backend tests (pytest-xdist, 16 workers), 99 frontend tests (Vitest).
Built in 3 days total (v1.0: 2026-02-15→16, v1.1: 2026-02-17), 28 plans across 10 phases.

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
| Textual TUI → React web dashboard | Rich operator interface with keybindings and visual feedback | ✓ Good — replaced TUI with web dashboard post-v1.0 |
| Groq fallback for commentary | Gemini rate-limited at scale; Groq provides fast fallback | ✓ Good — transparent failover, no quality loss |
| Detached asyncio tasks for display/reveals | Score reveals and display pushes must not block event bus | ✓ Good — consistent pattern across scoring and deliberation |
| Groq scoring via OpenAI-compatible SDK | No separate groq dependency, JSON mode for reliable output | ✓ Good — base_url override, response_format enforcement |
| asyncio.wait for MoE timeout | Partial results when providers are slow, 15s timeout | ✓ Good — replaces gather, cancels slow providers cleanly |
| connectionState tri-state | Distinguish initial connect from reconnect (prevents banner flash) | ✓ Good — 'connecting'→'connected'→'reconnecting' |
| ReplayProvider for rehearsal | Canned scoring with realistic varied scores for full pipeline testing | ✓ Good — validates MoE path without API keys |

---
*Last updated: 2026-02-17 after v1.1 milestone complete*
