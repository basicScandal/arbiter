# Requirements: Arbiter

**Defined:** 2026-02-15
**Core Value:** Produce fair, defensible scores that hold up alongside human judge scores — while being entertaining and resistant to prompt injection from a security-savvy audience.

## v1 Requirements

Requirements for NEBULA:FOG 2026. Each maps to roadmap phases.

### Input Processing

- [ ] **INPUT-01**: System captures live camera feed from venue at sufficient frame rate for slide/code readability
- [ ] **INPUT-02**: System captures live audio from presenter and transcribes speech to text
- [ ] **INPUT-03**: System extracts key frames from video (slides, code, terminal output) for analysis
- [ ] **INPUT-04**: Operator can start and stop demo capture per team with clear lifecycle boundaries
- [ ] **INPUT-05**: System processes camera and audio in real-time during the demo (not post-hoc)

### Prompt Injection Defense

- [ ] **DEF-01**: System uses dual-LLM architecture — quarantined model processes raw input, privileged model generates output
- [ ] **DEF-02**: System scans captured frames via OCR for visual injection attempts (hidden text on slides)
- [ ] **DEF-03**: System scans transcribed speech for verbal injection attempts
- [ ] **DEF-04**: When injection is detected, system generates a public roast of the attempt for audience entertainment
- [ ] **DEF-05**: All injection attempts are logged with timestamp, type (visual/verbal), and content for scoring notes

### Commentary & Persona

- [ ] **PERS-01**: System maintains a consistent Simon Cowell-meets-hacker personality across all demos
- [ ] **PERS-02**: System generates post-demo commentary that is adversarial and funny without targeting the person
- [ ] **PERS-03**: System generates Q&A questions when human judges defer to Arbiter during Q&A
- [ ] **PERS-04**: TTS voice output conveys emotional variety — sarcasm, surprise, genuine approval, disappointment

### Scoring

- [ ] **SCORE-01**: System scores each demo against official rubric (technical execution 40%, innovation 30%, demo quality 30%)
- [ ] **SCORE-02**: System displays per-demo score card to audience after each demo
- [ ] **SCORE-03**: Scoring pipeline is architecturally isolated from LLM commentary path (injection cannot affect scores)
- [ ] **SCORE-04**: System applies track-specific criteria (SHADOW::VECTOR, SENTINEL::MESH, ZERO::PROOF, ROGUE::AGENT)
- [ ] **SCORE-05**: Scores include per-criterion breakdown with brief justification

### Output & Display

- [ ] **OUT-01**: System speaks commentary and scores via TTS through venue speakers
- [ ] **OUT-02**: System displays commentary and scores as text on a screen visible to audience
- [ ] **OUT-03**: System has TTS failover — if primary provider fails, secondary activates automatically
- [ ] **OUT-04**: Score reveals are presented with dramatic timing and theatrical flair

### Memory & Deliberation

- [ ] **MEM-01**: System stores structured observations for each demo (extracted facts, not raw input)
- [ ] **MEM-02**: System performs comparative deliberation across all demos at end of event
- [ ] **MEM-03**: System produces final rankings with reasoning that human judges can review and discuss

### Venue Reliability

- [ ] **REL-01**: System handles network interruptions gracefully without crashing
- [ ] **REL-02**: System has clear degraded-mode behavior (text-only if TTS fails, cached responses if LLM is slow)
- [ ] **REL-03**: Operator can manually override or pause Arbiter at any time

## v2 Requirements

### Real-Time Commentary

- **RT-01**: System generates live commentary DURING demos (not just after)
- **RT-02**: Commentary timing controller ensures Arbiter doesn't talk over presenter

### Advanced Features

- **ADV-01**: Injection attempt scoreboard displayed to audience
- **ADV-02**: Post-hoc score recalibration across all demos to correct for position/order bias
- **ADV-03**: Audience interaction features (live reactions, polls)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time commentary during demos | High complexity, deferred to v2 — post-demo commentary sufficient for v1 |
| Self-hosted LLM | Timeline constraint — cloud APIs provide better quality in 2 weeks |
| Mobile app | Venue deployment only, no remote access needed |
| Automated prize distribution | Arbiter scores, humans handle logistics |
| Post-event analytics dashboard | Focus is live event performance |
| Audience chat integration | Massive injection surface, not worth the risk |
| Repository/code scanning | Attack surface too large, camera captures code on screen |
| Multi-language support | English-only event |
| Voice input from audience | Venue acoustics + injection risk |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INPUT-01 | Phase 1 | Pending |
| INPUT-02 | Phase 1 | Pending |
| INPUT-03 | Phase 1 | Pending |
| INPUT-04 | Phase 1 | Pending |
| INPUT-05 | Phase 1 | Pending |
| DEF-01 | Phase 2 | Pending |
| DEF-02 | Phase 2 | Pending |
| DEF-03 | Phase 2 | Pending |
| DEF-04 | Phase 2 | Pending |
| DEF-05 | Phase 2 | Pending |
| PERS-01 | Phase 3 | Pending |
| PERS-02 | Phase 3 | Pending |
| PERS-03 | Phase 3 | Pending |
| PERS-04 | Phase 6 | Pending |
| SCORE-01 | Phase 4 | Pending |
| SCORE-02 | Phase 4 | Pending |
| SCORE-03 | Phase 4 | Pending |
| SCORE-04 | Phase 4 | Pending |
| SCORE-05 | Phase 4 | Pending |
| OUT-01 | Phase 3 | Pending |
| OUT-02 | Phase 3 | Pending |
| OUT-03 | Phase 6 | Pending |
| OUT-04 | Phase 4 | Pending |
| MEM-01 | Phase 5 | Pending |
| MEM-02 | Phase 5 | Pending |
| MEM-03 | Phase 5 | Pending |
| REL-01 | Phase 6 | Pending |
| REL-02 | Phase 6 | Pending |
| REL-03 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 29 total
- Mapped to phases: 29
- Unmapped: 0

---
*Requirements defined: 2026-02-15*
*Last updated: 2026-02-15 after roadmap creation*
