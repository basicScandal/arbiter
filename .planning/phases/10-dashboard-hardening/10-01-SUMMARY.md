---
phase: 10-dashboard-hardening
plan: 01
subsystem: api, ui
tags: [fastapi, websocket, zustand, react, health-monitoring, scoring]

# Dependency graph
requires:
  - phase: 06-operator-dashboard
    provides: WebOperator WS handler, operatorStore, useOperatorSocket hook, protocol types
  - phase: 04-scoring-engine
    provides: ScoringComplete event, DemoScorecard model
  - phase: 06-groq-fallback
    provides: ServiceHealth singleton with get_status()
provides:
  - GET /api/health HTTP endpoint returning ServiceHealth data
  - WebSocket health push every 1s alongside counters
  - Health push on new WS connection (prevents stale data after reconnect)
  - Scorecard extraction from scoring_complete events over WS
  - HealthMessage protocol type in ServerMessage union
  - connectionState tri-state (connecting/connected/reconnecting) in Zustand store
  - health and lastScorecard state fields in store with dispatch handlers
  - setConnectionState hook transitions replacing setConnected in useOperatorSocket
affects: [10-dashboard-hardening plan 02 (UI components consume these interfaces)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy import of default_health inside endpoint/loop functions (avoids circular imports)"
    - "connectionState tri-state with 'connecting' initial value (prevents reconnect banner flash)"
    - "Backward-compatible setConnected that also updates connectionState"

key-files:
  created: []
  modified:
    - src/operator/web.py
    - operator-dashboard/src/types/protocol.ts
    - operator-dashboard/src/store/operatorStore.ts
    - operator-dashboard/src/hooks/useOperatorSocket.ts
    - operator-dashboard/src/store/__tests__/operatorStore.test.ts

key-decisions:
  - "Initial connectionState is 'connecting' (not 'reconnecting') to prevent banner flash on page load"
  - "setConnected kept for backward compat (ConnectionDot consumers), also syncs connectionState"
  - "Health pushed on same 1s loop as counters -- payload is tiny, simplicity over optimization"
  - "Scorecard rides on existing 'event' type (no new WS message type for scoring)"

patterns-established:
  - "Dual-path health exposure: HTTP for monitoring/curl, WS push for live dashboard"
  - "connectionState tri-state pattern for reconnect UX (connecting -> connected -> reconnecting)"

# Metrics
duration: 3min
completed: 2026-02-17
---

# Phase 10 Plan 01: Dashboard Data Layer Summary

**Health endpoint + WS health/scorecard push + connectionState tri-state plumbing for operator dashboard hardening**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-17T20:08:53Z
- **Completed:** 2026-02-17T20:12:01Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- GET /api/health endpoint exposes ServiceHealth data with ok/degraded status
- WebSocket pushes health messages every second and on new connections (prevents stale data)
- scoring_complete events now include full scorecard data (criteria, track_bonus, total_score)
- Frontend store tracks connectionState tri-state, health dict, and lastScorecard
- Hook drives connectionState transitions (connecting -> connected, connected -> reconnecting)

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend health endpoint + WS health push + scorecard extraction** - `18a270c` (feat)
2. **Task 2: Frontend protocol types + store state + hook connectionState** - `c5c8a33` (feat)

## Files Created/Modified
- `src/operator/web.py` - Added /api/health endpoint, health WS push in counter loop and _push_state, scorecard extraction in _on_event
- `operator-dashboard/src/types/protocol.ts` - Added HealthMessage interface, updated ServerMessage union
- `operator-dashboard/src/store/operatorStore.ts` - Extended with connectionState, health, lastScorecard fields and dispatch handlers
- `operator-dashboard/src/hooks/useOperatorSocket.ts` - Replaced setConnected with setConnectionState for tri-state transitions
- `operator-dashboard/src/store/__tests__/operatorStore.test.ts` - Updated beforeEach with new state fields

## Decisions Made
- Initial connectionState is 'connecting' (not 'reconnecting') to prevent reconnect banner flash on page load (Pitfall 2 from research)
- Kept setConnected for backward compatibility with ConnectionDot and other consumers; it also syncs connectionState
- Health pushed on same 1s loop as counters -- payload is tiny, simplicity wins over optimization
- Scorecard data rides on existing 'event' message type (no separate WS message type needed)
- Health pushed in _push_state for new connections to prevent stale data after reconnect (Pitfall 1 from research)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All data flow interfaces are stable for Plan 02 UI components
- connectionState available for ReconnectBanner component
- health state available for HealthPanel component
- lastScorecard available for ScorePanel enhancement
- All 92 existing tests continue to pass

---
*Phase: 10-dashboard-hardening*
*Completed: 2026-02-17*
