# Project Research Summary

**Project:** Arbiter - Live AI Judge Agent for NEBULA:FOG Security Hackathon
**Domain:** Real-time multimodal AI agent (live video + audio processing, commentary generation, scoring, TTS output)
**Researched:** 2026-02-15
**Confidence:** MEDIUM-HIGH

## Executive Summary

Arbiter is a live AI judge that processes real-time camera + audio feeds from security hackathon demos, generates entertaining commentary in a Simon Cowell-meets-hacker persona, and produces structured scores. This is a novel system combining real-time multimodal streaming (sports AI commentary architecture) with adversarially-robust LLM-as-judge scoring (hackathon judging systems) at a security event where the audience will actively attempt prompt injection.

The recommended approach uses Gemini 2.5 Flash Live API for native video+audio streaming, a dual-LLM architecture (quarantined LLM processes untrusted input, privileged LLM generates commentary) for injection defense, Cartesia for low-latency TTS, and a deterministic rubric-based scoring engine isolated from LLM commentary. The system must handle 24 demos (3-5 min each) with sub-2s commentary latency and maintain scoring consistency across the full event.

Key risks are multimodal prompt injection (security researchers will attack via slides and speech), latency stacking in the pipeline (camera-to-voice round trips must stay under 6s), and venue infrastructure failures (WiFi, audio feedback, TTS API timeouts). Mitigation requires architectural isolation (dual-LLM pattern from day one), streaming pipelines (not batch processing), and comprehensive failover strategies (backup TTS, offline mode, pre-cached responses).

## Key Findings

### Recommended Stack

The core architectural decision is using Gemini 2.5 Flash Live API for multimodal streaming. It provides native video (1 fps continuous) + audio streaming via WebSocket, built-in audio understanding without separate STT, system instruction support for persona, and context window compression for 3-5 min sessions. This is superior to OpenAI Realtime API which lacks native video streaming and requires manual frame injection.

**Core technologies:**
- **Gemini 2.5 Flash Live API (google-genai ~1.63.0)**: Real-time video+audio processing — native multimodal streaming with lowest integration complexity
- **Cartesia Sonic 3 (cartesia 3.0.0)**: Text-to-speech — 40ms TTFB, WebSocket streaming, emotion/laughter support for snarky persona
- **FastAPI (~0.129.0) + WebSocket**: Display server and text overlay — async-native, WebSocket for real-time commentary display
- **OpenCV (opencv-python ~4.13.0)**: Camera frame capture — industry standard for real-time video capture
- **Pydantic (~2.12.5)**: Data validation and scoring schemas — type-safe rubric definitions
- **Lakera Guard API**: Prompt injection defense layer — production-grade text injection detection (~50ms latency, ~$0.001/check)

**Critical constraint:** Gemini Live API sessions without compression are limited to 2 minutes (video fills 128k context at 258 tokens/sec). Must enable `contextWindowCompression` with sliding window for 3-5 min demos.

**Cost:** Extremely affordable at ~$0.21-0.37 per demo, ~$5-9 total for 24 demos.

### Expected Features

Research reveals no direct comparable system exists — Arbiter combines capabilities from sports AI commentators (real-time video commentary), LLM-as-judge systems (structured scoring), and adversarial AI security. The closest analogues lack integration of all three dimensions.

**Must have (table stakes):**
- **Multimodal demo ingestion** — camera + audio streaming; without this Arbiter cannot judge at all
- **Structured scoring with rubric** — NEBULA:FOG criteria (Technical Execution 40%, Innovation 30%, Demo Quality 30%); scores must be defensible
- **TTS voice output** — Arbiter must speak aloud to participate on the judging panel
- **Visual text display** — audience-facing scores and commentary on screen
- **Demo memory across 24 demos** — full-event recall for final deliberation; cannot rank without remembering earlier demos
- **Prompt injection defense** — architectural, not prompt-based; security audience will attack via slides and speech
- **Consistent persona** — Simon Cowell-meets-hacker character must hold across 24 demos

**Should have (differentiators):**
- **Real-time commentary during demos** — live reactions while demos run (signature capability; human judges sit silently)
- **Prompt injection detection + public roasting** — detect injection attempts and roast teams for trying (turns vulnerability into entertainment)
- **Comparative deliberation** — end-of-event analysis with specific cross-demo comparisons using full memory
- **Q&A question generation** — pointed questions based on what Arbiter actually observed

**Defer (v2+):**
- **Injection scoreboard** — gamified tracking of injection attempts (fun but not essential)
- **Dramatic score reveal timing** — pure entertainment polish
- **Emotional TTS variety** — sentiment-mapped voice parameters (nice to have but adds complexity)

### Architecture Approach

The architecture is built on the dual-LLM privilege separation pattern (Simon Willison): a Quarantined LLM (Q-LLM) processes untrusted input from camera/audio and extracts only structured observations; a Privileged LLM (P-LLM) receives sanitized observations and generates commentary with the full persona. The scoring engine is a third parallel path receiving verified observations directly — scores are computed deterministically from rubric criteria, completely isolated from LLM commentary output. This prevents any prompt injection from corrupting scores even if it influences commentary.

**Major components:**
1. **Capture Layer (Frame Grabber + Audio Capture)** — produces raw video frames (1-4 fps) and PCM audio; isolated from LLM logic
2. **Defense Layer (Q-LLM + Injection Detector)** — Q-LLM extracts structured observations from raw input; injection detector scans for residual injection patterns before forwarding
3. **Processing Layer (P-LLM + Scoring Engine)** — P-LLM generates commentary from safe observations; scoring engine applies rubric weights to structured data (no LLM in scoring path)
4. **Output Layer (TTS Engine + Text Display)** — streaming TTS starts audio before full text completes; WebSocket-based text display for audience
5. **Persistence Layer (Demo Memory + Score Store)** — structured observations and scores stored per-team; fed to deliberation engine at event end

**Data flow pattern:** Camera/mic → capture → Q-LLM → injection detector → [fork: P-LLM → commentary | scoring engine → scores] → outputs + memory. Untrusted input NEVER reaches P-LLM or scoring engine.

**Timing budget:** 5-12s total cycle (frame capture <50ms, audio transcription 1-3s, Q-LLM 2-5s, injection detection <100ms, P-LLM 2-4s, TTS TTFB 100-500ms). Fits within 10-20s commentary interval during demos.

### Critical Pitfalls

Research identified 8 critical pitfalls, prioritized by failure severity:

1. **Multimodal prompt injection via visual/audio channels** — Security researchers will embed instructions in slides, terminal output, QR codes, or speech. Single-LLM systems are vulnerable regardless of system prompt defenses. **Avoid:** Dual-LLM architecture (Q-LLM extracts, P-LLM never sees raw input). OCR frames separately, run injection detection on extracted text. Treat roasting injection attempts as entertainment feature.

2. **Pipeline latency stacking** — Each stage adds latency sequentially (capture 100ms + encoding 200ms + API 2-5s + TTS 1-2s + playback 500ms = 4-8s minimum; venue WiFi can spike to 10-15s). Dead silence kills audience engagement. **Avoid:** Stream-process during demos, not after. Use TTS WebSocket streaming. Pre-generate filler audio. Set 8s timeout with circuit breaker.

3. **Scoring drift across 24 demos** — LLM-as-judge research documents position bias, verbosity bias, calibration drift. Demo #1 scored harshly, demo #12 leniently, demo #24 inflated. **Avoid:** Structured rubric with 3-5 level descriptions per criterion. Include calibration examples. Score criteria independently. Run batch re-calibration pass after all demos.

4. **TTS failure during live performance** — Cloud TTS APIs hit rate limits, timeout, or produce garbled audio. Arbiter goes silent mid-event. **Avoid:** Two TTS providers with automatic failover (Cartesia primary, ElevenLabs fallback). Pre-generate common phrases. Build pronunciation dictionary for security terms. Test under network degradation.

5. **Persona derailment** — Two modes: (A) roast lands on personal characteristics, goes viral for wrong reasons; (B) over-correction makes persona bland, audience disengages. **Avoid:** Define "never touch" categories (no personal attacks). Roast only project/code/demo quality. Test with diverse review panel. Content filter between LLM output and TTS.

6. **Venue infrastructure collapse** — Conference WiFi fails, laptop overheats, Bluetooth speaker disconnects, camera freezes. Any single failure kills the show. **Avoid:** Bring 5G hotspot (two carriers), wired connections where possible, backup laptop, arrive 2+ hours early for venue test. Offline fallback mode with pre-generated content.

7. **System prompt extraction** — Attendees craft inputs to leak scoring rubric or defense mechanisms. Posted on Twitter during event. **Avoid:** Minimize info in Q-LLM prompt. Scoring criteria only in privileged context. Monitor outputs for prompt fragments. Prepare witty deflection responses.

8. **Audio echo loop** — Arbiter speaks through venue speakers, microphone picks up own voice, STT transcribes as new input, responds to own response. **Avoid:** Mute mic during TTS playback (state machine: LISTENING → PROCESSING → SPEAKING → LISTENING). Directional microphone, speakers facing away from mic.

## Implications for Roadmap

Based on research, the architecture dependencies and pitfall prevention requirements dictate a specific build order. The dual-LLM defense layer is the critical architectural decision that must be foundational — retrofitting privilege separation into a single-LLM system is effectively a rebuild.

### Phase 1: Foundation + Capture
**Rationale:** Every downstream component depends on having input data and event lifecycle management. The skeleton must establish the event bus pattern for component decoupling and demo state machine for timing control before any LLM integration.
**Delivers:** Event bus, demo state machine, frame grabber (camera → JPEG), audio capture (microphone → PCM), operator controls (start/stop/pause)
**Addresses:** Input layer for multimodal ingestion (table stakes feature)
**Avoids:** Monolithic pipeline anti-pattern (ARCHITECTURE.md)

### Phase 2: Defense Pipeline (Injection Protection)
**Rationale:** Processing layer depends on safe data. This is the most critical security boundary and must be architectural, not bolted on. Q-LLM integration and injection detection must exist before P-LLM or scoring engine receive any data.
**Delivers:** Q-LLM integration (multimodal → structured observations), injection detector (pattern matching + Lakera Guard), sanitizer (strips flagged content)
**Addresses:** Prompt injection defense (table stakes feature, Pitfall #1)
**Avoids:** Single-LLM vulnerability, storing raw untrusted content in memory
**Stack:** Gemini Flash or GPT-4o-mini for Q-LLM (fast, cheap), Lakera Guard API

### Phase 3: Commentary Pipeline
**Rationale:** This is the primary user-facing output and signature capability (real-time commentary differentiates from human judges). Can be built once defense layer provides safe observations. Streaming TTS is critical for latency mitigation.
**Delivers:** P-LLM integration (commentary generation), TTS engine (Cartesia WebSocket streaming), text display (WebSocket to browser), commentary prompts and persona
**Addresses:** Real-time commentary (differentiator), TTS voice output (table stakes), visual display (table stakes), consistent persona (table stakes)
**Avoids:** Latency stacking (Pitfall #2), persona derailment (Pitfall #5), TTS failure (Pitfall #4)
**Stack:** Claude Sonnet/Opus or Gemini Pro for P-LLM (quality matters), Cartesia Sonic 3 with ElevenLabs failover

### Phase 4: Scoring System
**Rationale:** Can be built in parallel with Phase 3 since both consume defense layer output but are otherwise independent. Scoring isolation is architectural — scores computed from structured observations, not LLM commentary.
**Delivers:** Scoring rubric definition (NEBULA:FOG criteria), scoring engine (deterministic, weighted), score store (persistence), score display (scorecard UI)
**Addresses:** Structured scoring (table stakes), per-demo score card (table stakes)
**Avoids:** LLM-generated scores anti-pattern, scoring drift (Pitfall #3)
**Stack:** Pydantic for rubric schemas, SQLite or JSON for score store

### Phase 5: Memory + Deliberation
**Rationale:** Requires all other components working. Demo memory stores sanitized observations (never raw input) and scores per-team. Deliberation engine loads all 24 memories for comparative analysis at event end.
**Delivers:** Demo memory store (per-team structured summaries), deliberation engine (comparative analysis prompt), final results display
**Addresses:** Demo memory (table stakes), comparative deliberation (differentiator), Q&A question generation (differentiator)
**Avoids:** Storing raw untrusted content in memory (anti-pattern)

### Phase 6: Hardening + Venue Prep
**Rationale:** Stress-test, optimize, and prepare for real-world conditions. Red team the injection defenses. Test under venue-like conditions (throttled network, audio feedback). Build failover and offline modes.
**Delivers:** Injection attack testing, latency optimization (parallel processing), TTS failover verification, venue simulation testing, offline fallback mode, operator dashboard
**Addresses:** All pitfalls under real conditions
**Avoids:** Venue infrastructure collapse (Pitfall #6), TTS failure (Pitfall #4), audio echo (Pitfall #8)

### Phase Ordering Rationale

- **Defense before processing:** The dual-LLM boundary is architectural. Building P-LLM or scoring engine before Q-LLM exists forces a single-LLM pattern that must be torn out later.
- **Streaming from the start:** Latency mitigation (Pitfall #2) requires streaming TTS and pipelined processing. Batch-based architecture cannot be patched to stream — it's a rebuild.
- **Parallel after foundation:** Phase 3 (commentary) and Phase 4 (scoring) can run in parallel once Phase 2 (defense) delivers safe data. Both consume the same input, both write to memory, neither depends on the other.
- **Hardening is a phase, not tasks:** Venue conditions (WiFi degradation, audio feedback, hardware failures) cannot be tested in isolation. Requires dedicated phase with full end-to-end runs.

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 2 (Defense Pipeline):** Lakera Guard API integration details, OCR extraction from frames (Tesseract vs PaddleOCR), optimal Q-LLM prompt structure for extraction vs defense
- **Phase 3 (Commentary Pipeline):** Cartesia WebSocket streaming protocol, TTS failover implementation patterns, commentary timing controller logic (when to speak vs stay silent)
- **Phase 6 (Hardening):** Venue-specific AV integration, offline mode architecture (what can work without internet), circuit breaker patterns for LLM APIs

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Foundation):** Event bus (Node.js EventEmitter), demo state machine (well-documented pattern), OpenCV frame capture (standard)
- **Phase 4 (Scoring):** Pydantic schemas (standard), deterministic rubric scoring (well-researched in LLM-as-judge literature)
- **Phase 5 (Memory):** Append-only structured storage (standard pattern)

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Gemini Live API capabilities verified via official docs; session limits need hands-on validation. TTS latency specs confirmed. Version compatibility checked on PyPI. |
| Features | MEDIUM | Novel domain (no exact comparable). Synthesized from adjacent systems (sports commentary + LLM-as-judge + adversarial security). Table stakes vs differentiators based on venue requirements and research analogues. |
| Architecture | MEDIUM | Dual-LLM pattern well-documented (Simon Willison, Google DeepMind CaMeL). Real-time multimodal streaming patterns exist (StreamMind, LiveCC). Integration of both is novel but components are proven. |
| Pitfalls | MEDIUM-HIGH | Prompt injection research is extensive (OWASP, academic papers). Latency challenges well-documented in real-time AI literature. Scoring drift quantified in LLM-as-judge studies. Venue infrastructure failures are universal. |

**Overall confidence:** MEDIUM-HIGH

The individual components (Gemini Live API, dual-LLM pattern, LLM-as-judge scoring, real-time TTS) are all established technologies with clear documentation. The risk is in integration complexity and the novel combination of real-time multimodal streaming + adversarial robustness + live event constraints. No comparable system exists to learn from directly.

### Gaps to Address

**Gemini Live API session management under load:** Documentation describes context window compression and session resumption, but real-world behavior under 24 consecutive 3-5 min sessions needs hands-on validation. Plan Phase 1 to include extended session testing (run 10+ mock demos consecutively).

**Injection detection false positive/negative rates:** Lakera Guard has high confidence ratings, but defense effectiveness against sophisticated visual injection (steganography, adversarial patterns) is unverified. Plan Phase 2 to include red team testing with security-minded testers crafting visual and audio injection payloads.

**TTS quality for security terminology:** Cartesia and ElevenLabs pronunciation of technical terms (SIEM, XSS, SSRF, k8s, CVE, OIDC) needs testing. Plan Phase 3 to build pronunciation dictionary and test all rubric-related terms.

**Venue WiFi latency under conference load:** Documented latency is 50-500ms typical, but conference WiFi with 200+ attendees is unpredictable. Plan Phase 6 to test with mobile hotspot as primary internet and treat venue WiFi as fallback.

**Scoring calibration with NEBULA:FOG rubric:** LLM-as-judge calibration research is general-purpose. Specific calibration examples for security hackathon demos (exploit complexity, threat model rigor, defense effectiveness) need to be crafted. Plan Phase 4 to create rubric-specific calibration examples in collaboration with human judges.

## Sources

### Primary (HIGH confidence)
- [Gemini Live API documentation](https://ai.google.dev/gemini-api/docs/live) — Session management, capabilities
- [Gemini Live API session management](https://ai.google.dev/gemini-api/docs/live-session) — Duration limits, compression, resumption
- [Simon Willison: Design Patterns for Securing LLM Agents](https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/) — Dual-LLM privilege separation
- [OWASP LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) — Defense taxonomy
- [Multimodal Prompt Injection Attacks](https://arxiv.org/html/2509.05883v1) — Visual/audio injection vectors
- [Cartesia Sonic 3](https://docs.cartesia.ai/build-with-cartesia/tts-models/latest) — Latency specs, capabilities
- [ElevenLabs Flash v2.5](https://elevenlabs.io/docs/overview/models) — Model specs, streaming
- PyPI version checks (2026-02-15) — google-genai 1.63.0, cartesia 3.0.0, elevenlabs 2.35.0, opencv-python 4.13.0

### Secondary (MEDIUM confidence)
- [Cerebrium AI Commentator](https://www.cerebrium.ai/blog/creating-a-realtime-ai-commentator-with-cerebrium-livekit-and-cartesia) — Real-time commentary architecture (~700ms latency)
- [Microsoft Research StreamMind](https://www.microsoft.com/en-us/research/articles/streammind-ai-system-that-responds-to-video-in-real-time/) — Video commentary gating network
- [Google DeepMind CaMeL](https://arxiv.org/abs/2503.18813) — Capability-based security evolution of dual-LLM
- [Adversarial Attacks on LLM-as-a-Judge](https://arxiv.org/abs/2504.18333) — Attack success rates (30-73% against undefended)
- [LLM-as-Judge vulnerability to prompt injection](https://arxiv.org/abs/2505.13348) — Pairwise comparison more robust
- [LLM-as-Judge Guide (Label Your Data)](https://labelyourdata.com/articles/llm-as-a-judge) — Rubric-based methodology
- [Lakera Guard documentation](https://docs.lakera.ai/docs/quickstart) — Integration guide
- [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime) — Alternative architecture reference
- [ElevenLabs latency optimization](https://elevenlabs.io/docs/developers/best-practices/latency-optimization) — 75ms TTFB with WebSocket

### Tertiary (LOW confidence, needs validation)
- [Deepgram vs Whisper comparison](https://deepgram.com/learn/whisper-vs-deepgram) — Vendor source, STT benchmarks
- [OpenAI Realtime vs Gemini Live comparison](https://skywork.ai/blog/agent/openai-realtime-api-vs-google-gemini-live-2025/) — Feature comparison (third-party analysis)
- [ETHGlobal AIJudge](https://ethglobal.com/showcase/aijudge-oeihx) — Async hackathon judging (limited detail)

---
*Research completed: 2026-02-15*
*Ready for roadmap: yes*
