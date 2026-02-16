# Arbiter

## What This Is

Arbiter is a live AI judge agent for the NEBULA:FOG 2026 hackathon — a security-focused hackathon where ~24 teams demo AI x Security projects. Arbiter sits on a panel alongside human judges, watches 3-5 minute live demos via camera + audio, delivers real-time commentary with a Simon Cowell-meets-hacker personality, scores projects using the official judging criteria, and participates in deliberation with full memory of all demos. It speaks via TTS and displays text on screen for audience visibility.

## Core Value

Arbiter must produce fair, defensible scores that hold up alongside human judge scores — while being entertaining and resistant to prompt injection from a security-savvy audience that will absolutely try to exploit it.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Live multimodal input processing (camera + audio from demos)
- [ ] Real-time commentary generation during/after demos
- [ ] TTS voice output + text display for audience
- [ ] Scoring against official NEBULA:FOG criteria (track awards, cross-track awards)
- [ ] Prompt injection defense (visual and verbal vectors)
- [ ] Injection detection with public roasting and logging
- [ ] Simon Cowell-meets-hacker personality (adversarial, funny, respects talent)
- [ ] Quick reaction score card after each demo
- [ ] Full demo memory for final comparative deliberation
- [ ] Q&A question generation (activated when human judges defer to Arbiter)
- [ ] Per-demo scoring notes for judge panel review

### Out of Scope

- Mobile app — this is a venue deployment
- Self-hosted LLM — will use cloud APIs for quality within tight timeline
- Automated prize distribution — Arbiter scores, humans handle logistics
- Post-event analytics dashboard — focus is live event performance

## Context

- **Event:** NEBULA:FOG 2026 hackathon, March 2026 (~2 weeks to build)
- **Audience:** Security researchers, hackers, builders — technically sophisticated and adversarial
- **Panel:** Arbiter is one of several judges; human judges can defer Q&A to it
- **Voting power:** Equal voting member — scores count toward prize decisions
- **Demo count:** ~24 projects expected (based on 2025 numbers)
- **Tracks:** SHADOW::VECTOR (attack), SENTINEL::MESH (defense), ZERO::PROOF (privacy), ROGUE::AGENT (novel)
- **Prize pool:** $5,000+ across track awards, cross-track awards, sponsor challenges, and recognition
- **Prompt injection is part of the fun:** Audience will try to exploit Arbiter; successful roasts of injection attempts add to the entertainment value
- **Simon Willison techniques:** Use established prompt injection defense patterns (dual-LLM, input sanitization, system prompt hardening)

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
| Multimodal LLM for vision+audio processing | Need to understand slides, code, and speech simultaneously | — Pending |
| Separate scoring from commentary generation | Injection defense is easier when scoring pipeline is isolated | — Pending |
| Simon Willison dual-LLM pattern for injection defense | Proven technique: one model processes input, another evaluates safety | — Pending |
| Camera + audio input (not screen share) | Physical venue setup, more natural judge experience | — Pending |
| Independent scoring with deliberation memory | Fair per-demo scoring but enables comparative analysis at end | — Pending |

---
*Last updated: 2026-02-15 after initialization*
