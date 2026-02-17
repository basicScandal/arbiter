# Phase 10: Dashboard Hardening - Research

**Researched:** 2026-02-17
**Domain:** WebSocket resilience, health monitoring, real-time event forwarding (React + Python/FastAPI)
**Confidence:** HIGH

## Summary

Phase 10 hardens the operator dashboard for live venue reliability. The codebase is already well-structured for all three requirements: DASH-01 (reconnect indicator), DASH-02 (health endpoint), and DASH-03 (scoring event forwarding). The existing `useOperatorSocket` hook already implements exponential backoff reconnection and sets a `connected` boolean in Zustand state. The `ConnectionDot` component already renders green/red based on that boolean. The `ServiceHealth` singleton (`default_health`) already tracks per-component health with `get_status()`. The `ScoringComplete` and `ScoreRevealed` events already fire on the event bus, and the `WebOperator._on_event` handler already broadcasts all events to operator clients.

The work is primarily: (1) enhancing the reconnect UX from a small dot to a visible banner/overlay, (2) adding a `/api/health` HTTP endpoint on the FastAPI server that returns `default_health.get_status()`, plus a new `HealthMessage` WebSocket message type so the dashboard receives health pushes, (3) extending the operator store and adding a `HealthPanel` component to display per-component status, and (4) enhancing the `ScorePanel` to actually render scoring data from `scoring_complete` events instead of the placeholder "Awaiting judgment..." text.

**Primary recommendation:** Leverage the existing infrastructure heavily -- this is a wiring/UI phase, not a new-architecture phase. The backend changes are minimal (one HTTP endpoint, one new WS message type, minor additions to `_on_event`). The bulk of work is React component development and testing.

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | ^19.1.1 | Dashboard UI framework | Already in use |
| Zustand | ^5.0.11 | State management | Already in use, handles WS dispatch |
| Tailwind CSS | ^4.1.18 | Styling | Already in use with custom @theme |
| Framer Motion | ^12.34.0 | Animations | Already installed, use for reconnect banner transitions |
| FastAPI | (Python) | WebSocket + HTTP server | Already serves `/ws/operator`, add `/api/health` |
| Vitest | ^4.0.18 | Frontend testing | Already configured with jsdom + testing-library |

### Supporting (No New Dependencies Needed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @testing-library/react | ^16.3.2 | Component testing | Already installed for dashboard tests |
| pytest | (Python) | Backend testing | Already installed for Python tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom reconnect logic | `reconnecting-websocket` npm package | Existing hook already works; adding a dep for 30 lines of logic is unnecessary |
| SSE for health | WebSocket health pushes | WebSocket already open; SSE would be a second connection. Use WS. |
| Polling `/api/health` from dashboard | Push via WS | Polling adds latency and load. Push is better for live ops. Do BOTH: HTTP for diagnostics, WS for dashboard. |

**Installation:**
```bash
# No new dependencies needed -- everything is already installed
```

## Architecture Patterns

### Current Architecture (What Exists)

```
Backend (Python/FastAPI):
  src/operator/web.py          # WebOperator: WS handler, event broadcast, command handling
  src/commentary/display_server.py  # DisplayServer: FastAPI app, WS connections
  src/resilience/health.py     # ServiceHealth: per-component health tracking (singleton)
  src/scoring/pipeline.py      # ScoringPipeline: publishes ScoringComplete events
  src/scoring/models.py        # ScoringComplete, ScoreRevealed event types

Frontend (React/TypeScript):
  operator-dashboard/src/
  +-- hooks/useOperatorSocket.ts    # WS connection with exponential backoff
  +-- store/operatorStore.ts        # Zustand store, dispatch handles state/event/counters/result
  +-- types/protocol.ts             # ServerMessage type union
  +-- components/ConnectionDot.tsx  # Green/red dot based on `connected` state
  +-- panels/ScorePanel.tsx         # Placeholder -- "Awaiting judgment..."
```

### Target Architecture (What Phase 10 Adds)

```
Backend additions:
  src/operator/web.py         # ADD: /api/health endpoint, health push in counter loop
                              # ADD: scoring_complete event enrichment with scorecard data

Frontend additions:
  operator-dashboard/src/
  +-- components/ReconnectBanner.tsx  # NEW: Visible overlay when disconnected
  +-- panels/HealthPanel.tsx          # NEW: Per-component health status display
  +-- panels/ScorePanel.tsx           # ENHANCE: Render actual scoring data
  +-- types/protocol.ts               # ADD: HealthMessage type
  +-- store/operatorStore.ts          # ADD: health state, scoring state
```

### Pattern 1: Reconnect Banner with Connection State
**What:** Replace the small ConnectionDot with a prominent overlay/banner when WebSocket is disconnected. Keep the dot for "connected" state, add a banner for "reconnecting" state.
**When to use:** Any operator-facing dashboard that must survive WiFi blips.
**Implementation approach:**
```typescript
// The existing useOperatorSocket already handles reconnection.
// We need to add a "reconnecting" state (not just connected/disconnected).
// The hook already tracks backoff and reconnect timer.

// Add to store:
connectionState: 'connected' | 'reconnecting' | 'disconnected'

// In useOperatorSocket, track state transitions:
// ws.onopen  -> 'connected'
// ws.onclose -> 'reconnecting' (if not unmounted)
// cleanup    -> 'disconnected'

// ReconnectBanner component:
// Shows animated overlay when connectionState !== 'connected'
// Uses framer-motion for smooth slide-in/slide-out
```

### Pattern 2: Health Endpoint + WebSocket Push (Dual Path)
**What:** Expose health via HTTP GET `/api/health` (for curl/monitoring) AND push health status over existing WS connection every N seconds (for dashboard).
**When to use:** When operators need both programmatic health checks and live dashboard visibility.
**Implementation approach:**
```python
# In WebOperator._register_routes(), add:
@app.get("/api/health")
async def health_check():
    from src.resilience.health import default_health
    return {
        "status": "ok",
        "services": default_health.get_status(),
        "failure_counts": {
            svc: default_health.failure_count(svc)
            for svc in default_health._healthy
        }
    }

# In WebOperator._push_counters_loop(), also push health:
health_data = default_health.get_status()
await self._broadcast_to_operators({
    "type": "health",
    "services": health_data,
})
```

### Pattern 3: Scoring Event Forwarding to Dashboard
**What:** When `scoring_complete` events arrive, extract scorecard data and broadcast to operator clients. The `ScorePanel` renders the scorecard in real-time.
**When to use:** The event is already flowing through `_on_event` (which broadcasts all events). The issue is that `_on_event` only extracts limited fields. We need to extract the full scorecard from `ScoringComplete` events.
**Implementation approach:**
```python
# In WebOperator._on_event(), add special handling for scoring_complete:
if event.event_type == "scoring_complete" and hasattr(event, "scorecard"):
    scorecard = event.scorecard
    event_data["data"]["scorecard"] = {
        "team_name": scorecard.team_name,
        "track": scorecard.track,
        "total_score": scorecard.total_score,
        "criteria": [
            {
                "name": c.name,
                "score": c.score,
                "weight": c.weight,
                "justification": c.justification,
            }
            for c in scorecard.criteria
        ],
        "track_bonus": {
            "name": scorecard.track_bonus.name,
            "score": scorecard.track_bonus.score,
            "weight": scorecard.track_bonus.weight,
            "justification": scorecard.track_bonus.justification,
        } if scorecard.track_bonus else None,
    }
```

### Anti-Patterns to Avoid
- **Reconnect flooding:** Do NOT remove the exponential backoff. The existing hook correctly caps at 10s. Do NOT add a "reconnect now" button that bypasses backoff -- it would DDoS the server.
- **Health polling from frontend:** Do NOT add `setInterval(fetch('/api/health'), 1000)` in the dashboard. The WS push handles this. The HTTP endpoint is for external monitoring only.
- **Blocking health checks:** Do NOT make health checks call external services (e.g., pinging Gemini). `ServiceHealth.get_status()` is a fast in-memory read. Keep it that way.
- **Scorecard in event stream:** The event stream already shows "scoring_complete" as a line item. The detailed scorecard should go to the dedicated ScorePanel, not inline in the event stream.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket reconnection | Custom reconnect logic | Existing `useOperatorSocket` backoff | Already works, tested, correct |
| Health tracking | New health tracker | `ServiceHealth` / `default_health` singleton | Already tracks TTS; just needs more services and an exposure endpoint |
| Animation transitions | CSS keyframes for banner | `framer-motion` (already installed) | Handles mount/unmount transitions cleanly, already a dependency |
| State management for health/scores | React Context or prop drilling | `Zustand` store extension | Pattern already established for all other dashboard state |

**Key insight:** This phase is almost entirely about wiring existing infrastructure together and building new React components. There is zero new Python architecture needed -- just a few method additions to `WebOperator`.

## Common Pitfalls

### Pitfall 1: Stale Health Data After Reconnect
**What goes wrong:** Dashboard reconnects after WiFi blip but health panel shows stale data from before disconnect.
**Why it happens:** Health is only pushed periodically. After reconnect, the dashboard waits for the next push cycle.
**How to avoid:** Push health status as part of `_push_state()` which fires on every new WS connection. The existing pattern already does this for demo state -- do the same for health.
**Warning signs:** Health panel shows green after a 30-second disconnect when TTS was marked unhealthy during that time.

### Pitfall 2: Reconnect Banner Flicker on Page Load
**What goes wrong:** On initial page load, the banner briefly flashes "Reconnecting..." before the first WS connects.
**Why it happens:** Initial state is `connected: false`, and the banner renders before `ws.onopen` fires.
**How to avoid:** Use a `connectionState` that starts as `'connecting'` (not `'reconnecting'`). Only show the banner for `'reconnecting'`, not for initial `'connecting'`.
**Warning signs:** Every page load shows a brief reconnecting flash.

### Pitfall 3: Score Panel Races with Commentary
**What goes wrong:** Score appears on dashboard before Arbiter finishes speaking commentary.
**Why it happens:** `ScoringComplete` fires when scoring finishes, but `ScoreRevealed` fires after the theatrical reveal. The dashboard might show scores before the audience sees them.
**How to avoid:** Two options: (a) use `score_revealed` instead of `scoring_complete` for dashboard display, or (b) show scores on dashboard immediately (operator privilege -- they should see it before the audience). Recommendation: show immediately on operator dashboard with `scoring_complete` -- the operator SHOULD see scores before the audience.
**Warning signs:** Audience notices operator reacting to scores before they see them on the main display.

### Pitfall 4: Health Services Not Registered Until First Use
**What goes wrong:** Health panel shows no services initially because `ServiceHealth` only tracks services that have been explicitly `mark_healthy` or `mark_unhealthy`.
**Why it happens:** Currently only `cartesia_tts` is tracked via `default_health`. Gemini and scoring providers don't call `mark_healthy/unhealthy`.
**How to avoid:** Either (a) pre-register services in health on startup, or (b) have the health panel show a fixed list of known services and treat "untracked" as "unknown/not yet checked" rather than "missing".
**Warning signs:** Health panel is empty until TTS first connects.

### Pitfall 5: WebSocket Message Size for Scorecard Data
**What goes wrong:** Scorecard with detailed justifications could be several KB per event.
**Why it happens:** Each criterion has a `justification` string that could be 100+ words.
**How to avoid:** This is not actually a problem for WebSocket -- a few KB is well within limits. Just be aware that if you truncate justifications for display, do it on the frontend, not the backend.
**Warning signs:** None expected; just be aware of the data size.

## Code Examples

### Existing: useOperatorSocket reconnection (already working)
```typescript
// Source: operator-dashboard/src/hooks/useOperatorSocket.ts
// Already implements exponential backoff with MAX_BACKOFF_MS = 10_000
ws.onclose = () => {
  setConnected(false);
  wsRef.current = null;
  if (!unmounted) {
    reconnectTimer = setTimeout(() => {
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
      connect();
    }, backoffRef.current);
  }
};
```

### Existing: ServiceHealth.get_status() (already working)
```python
# Source: src/resilience/health.py
def get_status(self) -> dict[str, bool]:
    """Return current health status for all tracked services."""
    return {
        service: self.is_healthy(service) for service in self._healthy
    }
```

### Existing: ScoringComplete event (already fires)
```python
# Source: src/scoring/pipeline.py lines 98-100
if self._event_bus is not None:
    self._event_bus.publish(ScoringComplete(scorecard=scorecard))
```

### Existing: WebOperator._on_event broadcasts all events (already working)
```python
# Source: src/operator/web.py lines 115-155
# Already broadcasts all events to operator clients.
# scoring_complete events already appear in the dashboard event stream.
# What's missing: scorecard data extraction for the ScorePanel.
```

### Target: ReconnectBanner component pattern
```typescript
// New component using framer-motion for smooth transitions
import { AnimatePresence, motion } from "framer-motion";
import { useOperatorStore } from "../store/operatorStore";

export function ReconnectBanner() {
  const connectionState = useOperatorStore((s) => s.connectionState);
  const isReconnecting = connectionState === 'reconnecting';

  return (
    <AnimatePresence>
      {isReconnecting && (
        <motion.div
          initial={{ opacity: 0, y: -40 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -40 }}
          className="fixed top-0 inset-x-0 z-50 bg-event-injection/90 text-white text-center py-2 font-mono text-sm"
        >
          CONNECTION LOST -- RECONNECTING...
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

### Target: Health endpoint on FastAPI
```python
# Add to WebOperator._register_routes()
@app.get("/api/health")
async def health_endpoint():
    from src.resilience.health import default_health
    status = default_health.get_status()
    return {
        "status": "ok" if all(status.values()) else "degraded",
        "services": status,
    }
```

### Target: HealthPanel component pattern
```typescript
// New panel showing per-component health
export function HealthPanel() {
  const health = useOperatorStore((s) => s.health);

  return (
    <div className="glass-panel p-4 animate-border-glow">
      <h2 className="section-label mb-3">SYSTEM HEALTH</h2>
      {Object.entries(health).map(([service, healthy]) => (
        <div key={service} className="flex justify-between items-center py-1">
          <span className="text-text-dim text-xs uppercase">{service}</span>
          <span className={healthy ? "text-accent-capturing" : "text-event-injection"}>
            {healthy ? "ONLINE" : "DEGRADED"}
          </span>
        </div>
      ))}
    </div>
  );
}
```

### Target: Store extension for health + scoring
```typescript
// Add to OperatorState interface:
connectionState: 'connecting' | 'connected' | 'reconnecting';
health: Record<string, boolean>;
lastScorecard: {
  team_name: string;
  track: string;
  total_score: number;
  criteria: Array<{name: string; score: number; weight: number; justification: string}>;
  track_bonus: {name: string; score: number; weight: number; justification: string} | null;
} | null;

// Add to dispatch:
case 'health':
  set({ health: msg.services });
  break;

// In existing 'event' handler, also check for scoring_complete with scorecard data:
if (msg.event_type === 'scoring_complete' && msg.data?.scorecard) {
  set({ lastScorecard: msg.data.scorecard });
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Polling for WS reconnect | Exponential backoff with cap | Already implemented | No change needed |
| No health visibility | `ServiceHealth` singleton | Phase 6 | Just needs exposure endpoint |
| Scorecard via manual refresh | Event bus broadcast | Phase 4 | Just needs frontend rendering |

**Deprecated/outdated:**
- None -- the existing stack (React 19, Zustand 5, Tailwind 4, Vite 7) is current.

## Codebase Inventory (Existing vs. New)

### What Already Exists (DASH-01: Reconnect)
- `useOperatorSocket.ts`: Full reconnect with exponential backoff (1s -> 10s cap)
- `operatorStore.ts`: `connected: boolean` state, `setConnected()` action
- `ConnectionDot.tsx`: Green/red dot in header

### What Already Exists (DASH-02: Health)
- `src/resilience/health.py`: `ServiceHealth` class with `get_status()`, `failure_count()`
- `default_health` singleton: Tracks `cartesia_tts` health already
- Commentary pipeline: Calls `mark_healthy/unhealthy` on TTS operations

### What Already Exists (DASH-03: Scoring Events)
- `ScoringComplete` event: Fired by `ScoringPipeline._on_observation_verified()`
- `ScoreRevealed` event: Fired by `ScoringPipeline._reveal_score()`
- `WebOperator._on_event()`: Broadcasts ALL events to operator clients
- `EventStream.tsx`: Already renders `scoring_complete` in the event feed
- `ScorePanel.tsx`: Exists but is a placeholder ("Awaiting judgment...")

### What Needs to Be Built
1. **ReconnectBanner component** + store enhancement (`connectionState` enum)
2. **`/api/health` HTTP endpoint** on `WebOperator`
3. **Health WS push** in `_push_counters_loop()` or separate loop
4. **`HealthMessage` protocol type** + store `health` field
5. **HealthPanel component** for dashboard
6. **Scorecard data extraction** in `WebOperator._on_event()` for `scoring_complete`
7. **ScorePanel enhancement** to render actual scorecard data
8. **Tests** for all new components and backend changes

### Services to Track on Health Panel
| Service | Currently Tracked | Source |
|---------|-------------------|--------|
| `cartesia_tts` | YES | `default_health` via CommentaryPipeline |
| `gemini_live` | NO -- needs adding | GeminiSession connect/disconnect |
| `gemini_scoring` | NO -- needs adding | ScoringPipeline/ScoringEngine errors |
| `display_server` | NO -- needs adding | DisplayServer.start() success/fail |

Recommendation: For Phase 10, expose what `default_health` already tracks (TTS). Adding health tracking for Gemini and scoring is a separate concern (would require changes across multiple pipelines). The health panel should show tracked services dynamically from `get_status()` and treat an empty list as "all services nominal (no failures detected)."

## Open Questions

1. **Should the health panel show services not yet tracked?**
   - What we know: Currently only `cartesia_tts` is tracked. Gemini/scoring don't call `mark_healthy/unhealthy`.
   - What's unclear: Whether to add health tracking to Gemini/scoring in this phase.
   - Recommendation: Show what `default_health` exposes. If the health dict is empty, show "All systems nominal." Adding health tracking to more services is a natural follow-up but not required by DASH-02's letter ("health endpoint exposes ServiceHealth data for operator visibility").

2. **Should scoring results show on dashboard before or after audience sees them?**
   - What we know: `scoring_complete` fires before theatrical reveal. `score_revealed` fires after.
   - What's unclear: Whether the operator seeing scores early is a feature or a bug.
   - Recommendation: Use `scoring_complete` -- the operator dashboard is for the operator, not the audience. Early visibility is a feature. The operator needs to know the score before the reveal to prepare for any issues.

3. **Should the health push frequency match the counter push frequency (1s)?**
   - What we know: Counters push every 1 second. Health changes are rare (minutes apart, not seconds).
   - What's unclear: Whether 1s health pushes waste bandwidth.
   - Recommendation: Push health on the same 1s loop as counters. The payload is tiny (a few service names + booleans). Alternatively, push health only on change + on initial connect. The 1s loop is simpler and the cost is negligible.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `src/operator/web.py` -- WebOperator class, WS handler, event broadcasting
- Codebase analysis: `src/resilience/health.py` -- ServiceHealth class, get_status(), default_health singleton
- Codebase analysis: `operator-dashboard/src/hooks/useOperatorSocket.ts` -- Existing reconnect logic
- Codebase analysis: `operator-dashboard/src/store/operatorStore.ts` -- Zustand store, dispatch pattern
- Codebase analysis: `operator-dashboard/src/types/protocol.ts` -- Server message types
- Codebase analysis: `operator-dashboard/src/panels/ScorePanel.tsx` -- Current placeholder
- Codebase analysis: `src/scoring/pipeline.py` -- ScoringComplete event publishing
- Codebase analysis: `src/scoring/models.py` -- ScoringComplete, DemoScorecard models

### Secondary (MEDIUM confidence)
- Codebase analysis: `src/commentary/pipeline.py` -- ServiceHealth usage for TTS (only service currently tracked)
- Codebase analysis: `operator-dashboard/package.json` -- framer-motion already installed

### Tertiary (LOW confidence)
- None -- this phase is entirely codebase-driven, no external library research needed.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- everything is already installed, no new deps
- Architecture: HIGH -- all patterns are established, just extending them
- Pitfalls: HIGH -- identified from direct codebase analysis of existing code paths

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (30 days -- stable codebase, no fast-moving deps)
