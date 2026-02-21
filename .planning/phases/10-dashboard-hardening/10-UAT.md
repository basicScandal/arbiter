---
status: diagnosed
phase: 10-dashboard-hardening
source: [10-01-SUMMARY.md, 10-02-SUMMARY.md]
started: 2026-02-17T20:20:00Z
updated: 2026-02-17T20:35:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Health endpoint returns JSON
expected: Run `curl http://localhost:8080/api/health`. Response is JSON with "status" ("ok" or "degraded") and "services" dict of boolean values.
result: pass

### 2. Dashboard loads without reconnect banner flash
expected: Open the operator dashboard in browser and reload the page. There should be NO red "RECONNECTING" banner flash during initial load. The page should load cleanly.
result: pass

### 3. ConnectionDot shows green when connected
expected: With the server running and dashboard open, the connection indicator dot should be green and pulsing, indicating a healthy WebSocket connection.
result: pass

### 4. Reconnect banner appears on WS drop
expected: Kill the backend server (Ctrl+C) while the dashboard is open. A red banner reading "CONNECTION LOST — RECONNECTING..." should slide in from the top of the page.
result: pass

### 5. Reconnect banner disappears on reconnect
expected: Restart the server after it was stopped. The red reconnect banner should slide away smoothly once the WebSocket reconnects. No page refresh needed.
result: pass

### 6. HealthPanel shows system status
expected: On the dashboard right column (between Defense and Score panels), a "SYSTEM HEALTH" panel should be visible. If no services are tracked, it shows "All systems nominal". If services are registered with ServiceHealth, each shows ONLINE (green) or DEGRADED (red).
result: pass

### 7. ScorePanel shows awaiting state
expected: Before any demo has been scored, the Score panel should display "Awaiting judgment..." as placeholder text.
result: pass

### 8. ScorePanel renders live scorecard
expected: After a demo finishes scoring (or in rehearsal mode), the Score panel should update in real-time to show: team name, track name, a prominent total score out of 10, per-criterion breakdown with weights, and track bonus if applicable. No manual refresh needed.
result: issue
reported: "the commentary didn't finish. there is no way to reset, and the score hasn't shown"
severity: major

## Summary

total: 8
passed: 7
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "When a demo finishes scoring, the scoring result appears on the operator dashboard in real-time without manual refresh"
  status: failed
  reason: "User reported: the commentary didn't finish. there is no way to reset, and the score hasn't shown"
  severity: major
  test: 8
  root_cause: "operatorStore.ts missing lastScorecard reset when new demo starts — stale scorecard persists across demos, and if commentary hangs before scoring fires, ScorePanel never updates"
  fix_applied: "Added lastScorecard/scoringPhase/demoTimer reset on idle and capturing state transitions (operatorStore.ts lines 86-87)"
  fix_commit: "c55d631 (Tier 3 technical quality improvements)"
  status: fixed
  artifacts:
    - path: "operator-dashboard/src/store/operatorStore.ts"
      issue: "No lastScorecard reset in dispatch() when demoState transitions to capturing"
  missing: []
  debug_session: ".planning/debug/scoring-not-shown.md"
