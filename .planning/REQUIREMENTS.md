# Requirements: Arbiter

**Defined:** 2026-02-17
**Core Value:** Produce fair, defensible scores alongside human judges -- while being entertaining and resistant to prompt injection from a security-savvy audience.

## v1.1 Requirements

Requirements for v1.1 Reliability & Polish. Each maps to roadmap phases.

### Testing Infrastructure

- [ ] **TEST-01**: Test suite includes EventCollector fixture for reliable async event assertion without sleep
- [ ] **TEST-02**: Tests have pytest-timeout guards preventing hangs from unawaited tasks
- [ ] **TEST-03**: Autouse fixture resets module-level singletons between tests (rate limiter, health, default bus)
- [ ] **TEST-04**: Integration tests are marked and separable from unit tests
- [ ] **TEST-05**: Tests can run in parallel via pytest-xdist without interference
- [ ] **TEST-06**: API responses can be recorded and replayed via VCR.py cassettes

### E2E Pipeline Coverage

- [ ] **E2E-01**: Full pipeline chain test validates event flow from capture through deliberation
- [ ] **E2E-02**: MoE integration test validates multi-provider scoring with mock providers
- [ ] **E2E-03**: Event wiring regression tests verify all EventBus subscriptions are connected
- [ ] **E2E-04**: Multi-level event chain tests drain all create_task depths correctly

### Reliability & Fallbacks

- [ ] **REL-01**: GroqProvider implements LLMProvider for scoring fallback when Gemini is unavailable
- [ ] **REL-02**: MoE engine uses asyncio.wait with hard timeout instead of unbounded gather
- [ ] **REL-03**: Groq scoring fallback is calibrated in ScoreAggregator with empirical values

### Rehearsal Mode

- [ ] **RHS-01**: Synthetic capture feeds mock camera + audio events into EventBus without real hardware
- [ ] **RHS-02**: Replay provider returns canned LLM responses for deterministic rehearsal runs
- [ ] **RHS-03**: Operator can start rehearsal mode via CLI flag or dashboard command

### Dashboard Hardening

- [ ] **DASH-01**: WebSocket auto-reconnects with visual indicator showing connection state
- [ ] **DASH-02**: Health endpoint exposes ServiceHealth data for operator visibility
- [ ] **DASH-03**: Scoring events are forwarded to operator dashboard in real-time

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Live Experience

- **LIVE-01**: Real-time commentary during demos (not just post-demo)
- **LIVE-02**: Audience reaction tracking

### Advanced Scoring

- **ASCR-01**: Health-aware provider selection in MoE engine
- **ASCR-02**: Recorded demo replay from saved JSON fixtures of real demos
- **ASCR-03**: Post-event analytics dashboard

## Out of Scope

| Feature | Reason |
|---------|--------|
| Mobile app | Venue deployment only — web dashboard sufficient |
| Self-hosted LLM | Cloud APIs provide better quality within timeline |
| Audience chat integration | Massive injection surface, not worth the risk |
| Repository/code scanning | Attack surface too large, camera captures code on screen |
| Playwright browser E2E | Stretch goal, defer to v2 — unit + integration tests sufficient |
| Automated prize distribution | Arbiter scores, humans handle logistics |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TEST-01 | Phase 7 | Pending |
| TEST-02 | Phase 7 | Pending |
| TEST-03 | Phase 7 | Pending |
| TEST-04 | Phase 7 | Pending |
| TEST-05 | Phase 7 | Pending |
| TEST-06 | Phase 7 | Pending |
| E2E-01 | Phase 8 | Pending |
| E2E-02 | Phase 8 | Pending |
| E2E-03 | Phase 8 | Pending |
| E2E-04 | Phase 8 | Pending |
| REL-01 | Phase 9 | Pending |
| REL-02 | Phase 9 | Pending |
| REL-03 | Phase 9 | Pending |
| RHS-01 | Phase 9 | Pending |
| RHS-02 | Phase 9 | Pending |
| RHS-03 | Phase 9 | Pending |
| DASH-01 | Phase 10 | Pending |
| DASH-02 | Phase 10 | Pending |
| DASH-03 | Phase 10 | Pending |

**Coverage:**
- v1.1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0

---
*Requirements defined: 2026-02-17*
*Last updated: 2026-02-17 after roadmap creation*
