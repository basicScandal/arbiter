# Milestones

## v1.0 MVP (Shipped: 2026-02-16)

**Phases completed:** 6 phases, 19 plans
**Timeline:** 2 days (2026-02-15 → 2026-02-16)
**Stats:** 6,141 LOC Python, 113 files, 90 commits

**Delivered:** Live AI judge agent for NEBULA:FOG 2026 hackathon — watches demos via camera + audio, roasts prompt injection attempts, delivers Simon Cowell-meets-hacker commentary via TTS, scores against official rubric, and produces comparative rankings for deliberation.

**Key accomplishments:**
- Real-time camera + audio capture with Gemini Live API transcription and key frame detection
- Dual-LLM prompt injection defense with OCR visual scanning, verbal detection, and audience-facing roasts
- Simon Cowell-meets-hacker commentary via streaming Gemini + Cartesia TTS with per-sentence emotion control
- Isolated rubric-based scoring (40/30/30 weights, 4 track variants) with theatrical CSS-animated score reveals
- Per-demo memory storage and end-of-event comparative deliberation with Python-authoritative rankings
- Venue hardening with tenacity retry, TTS failover chain (Cartesia → macOS say → text-only), and operator pause/resume

**Git range:** `feat(01-01)` → `feat(06-03)`

---


## v1.1 Reliability & Polish (Shipped: 2026-02-17)

**Phases completed:** 4 phases (7-10), 9 plans
**Timeline:** 1 day (2026-02-17)
**Stats:** ~18K LOC Python, ~2.4K LOC TypeScript, 99 frontend tests, 371 parallel backend tests

**Delivered:** Hardened Arbiter for live event reliability — full test infrastructure with parallel execution, E2E pipeline coverage catching wiring regressions, Groq scoring fallback with MoE timeout hardening, rehearsal mode for zero-dependency dry runs, and operator dashboard with reconnect resilience, health monitoring, and live scoring.

**Key accomplishments:**
- Test infrastructure: 371 parallel tests across 16 xdist workers, 30s timeout guards, singleton reset fixtures, VCR cassettes
- E2E pipeline coverage: full chain tests (capture→deliberation), MoE 3-provider validation, subscriber count regression guards
- Groq scoring fallback with JSON mode + MoE timeout hardening (asyncio.wait with partial results on slow providers)
- Rehearsal mode: `--rehearsal` flag runs full demo cycle with SyntheticCapture + ReplayProvider, zero external dependencies
- Dashboard hardening: reconnect banner with framer-motion, health panel (ONLINE/DEGRADED), live scorecard rendering
- Gap closure: scorecard reset on new demo start preventing stale scores across teams

**Git range:** `feat(07-01)` → `fix(10-03)`

---

