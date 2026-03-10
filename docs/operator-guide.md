# Arbiter Operator Guide -- NEBULA:FOG 2026

## Event-Day Workflow

### 1. Pre-Event Setup

Start the system and verify everything works:

```bash
# Start the backend (serves both dashboards + API)
uv run arbiter

# Operator dashboard: http://localhost:8080/operator/
# Audience display:   http://localhost:8080/app/
# Health check:       http://localhost:8080/api/health
```

Verify in the operator dashboard:
- Connection dot shows green (WebSocket connected)
- Health panel shows "display server: ONLINE"
- State shows "STANDBY"

### 2. Running a Demo

For each team:

1. **Enter team name** in the text input
2. **Select track** from the dropdown:
   - `SHADOW::VECTOR` -- Offensive security / attack tools (bonus: Attack Effectiveness)
   - `SENTINEL::MESH` -- Defensive security / detection tools (bonus: Defense Robustness)
   - `ZERO::PROOF` -- Cryptography / privacy tools (bonus: Privacy Guarantees)
   - `ROGUE::AGENT` -- Wildcard / cross-domain (bonus: Originality Factor) -- default
3. **Click START** -- begins camera/audio capture via Gemini Live API
4. **Monitor vitals** -- watch frames, transcripts, attacks, clean observations
5. **Watch for timer warnings** at 90% and 100% of max duration (default 10 min)
6. **Click STOP** -- triggers defense pipeline, then scoring + commentary in parallel
7. **Wait for commentary** -- Arbiter speaks via TTS and streams text to audience
8. **Wait for score reveal** -- theatrical: intro, criteria one-by-one, then total
9. **Optionally press Q&A** -- generates targeted questions for the team
10. **Click NEXT TEAM** -- resets to idle, shows intermission leaderboard

### 3. Post-Demo Pipeline (what happens after STOP)

After clicking STOP, the pipeline runs automatically:

1. **Sanitizing** (~2s) -- Defense pipeline scans for injection, cleans observations
2. **Commentary** (~10-20s) -- Streaming sentences via TTS + display
3. **Scoring** (~5-15s) -- Multi-model consensus scoring (runs parallel with commentary)
4. **Score reveal** (~10-15s) -- Theatrical reveal after commentary finishes

Total wall-clock: ~25-40s from STOP to ready for NEXT TEAM.

### 4. Final Deliberation

After all demos are complete:

1. Click **DELIBERATE** -- triggers cross-demo analysis
2. Arbiter ranks all teams and generates a narrative summary
3. Audience display shows reverse-order reveal (worst to best)
4. Winner gets gold treatment with "WINNER" badge

### 5. Human Scoring

Human judges submit scores via API:

```bash
curl -X POST http://localhost:8080/api/human-score \
  -H "Content-Type: application/json" \
  -d '{"judge_name": "Judge1", "team_name": "TeamAlpha", "total_score": 8.5, "notes": "Great demo"}'
```

Blended scores: `GET /api/blended-scores` (default 70% AI + 30% human, configurable).

### 6. Export Results

```bash
# All teams with scores
curl http://localhost:8080/api/report-cards

# Full event data export
curl http://localhost:8080/api/export

# With audit trail
curl "http://localhost:8080/api/export?include_audit=true"

# Single team report card (HTML)
curl http://localhost:8080/api/report-card/TeamAlpha
```

## Track Reference

| Track | Focus | Bonus Criterion |
|-------|-------|-----------------|
| SHADOW::VECTOR | Offensive security, attack tools | Attack Effectiveness (10% bonus weight) |
| SENTINEL::MESH | Defensive security, detection | Defense Robustness (10% bonus weight) |
| ZERO::PROOF | Cryptography, privacy tools | Privacy Guarantees (10% bonus weight) |
| ROGUE::AGENT | Wildcard, cross-domain | Originality Factor (10% bonus weight) |

## Dashboard Visual Indicators

### Timer states
- **Idle** -- shows `--:--` in dim text (no demo active)
- **Capturing** -- shows elapsed time in green (demo in progress)
- **Paused** -- shows frozen elapsed time in default color
- **Stopped** -- shows final elapsed time in default color

### Button states
- **Active** -- normal button appearance, clickable
- **Pending** -- spinning indicator next to button text, all buttons disabled
- **Disabled** -- dimmed appearance (e.g., START without a team name)

### Connection banner
- **Connecting** -- amber banner at top: "CONNECTING..."
- **Reconnecting** -- red banner at top: "CONNECTION LOST -- RECONNECTING..."
- **Connected** -- no banner

### Command feedback
- Commands show a success/error toast for 3 seconds after the server responds.
- If the server does not respond within 10 seconds, the command times out and
  shows "Command timed out -- no response from server". Buttons re-enable.
- If you click a button while disconnected, you see "Not connected -- command not
  sent" immediately. The command is not queued.

## Troubleshooting

### Scoring shows 5.0 across all criteria
All LLM providers failed. The scorecard will show "Scoring error -- manual review required" in justifications. Use human scoring API to override.

### Commentary is empty or truncated
LLM streaming timed out after 30s. Partial sentences are preserved. Commentary delivered event still fires so scoring reveal proceeds normally.

### WebSocket disconnects
Dashboard auto-reconnects with exponential backoff (1s, 2s, 4s, 8s, 10s max).
Full state is resynced on every reconnect -- the client sends a `get_state`
request and the server pushes current state, health, and scoring phase. If the
operator laptop crashes mid-demo, restart the dashboard and the connection will
resume with current state.

The audience display also resyncs on reconnect. It sends `request_state` and the
server replays the current screen (commentary, scorecard, intermission, etc.).

### Buttons stuck / disabled
If buttons appear stuck in a disabled state, the command may have timed out. The
10-second timeout auto-clears `pendingCommand` and re-enables buttons. If this
happens repeatedly, check the WebSocket connection (look for the reconnect banner).

### "TTS unhealthy" in health panel
Cartesia API is down. System degrades to text-only commentary (display still works, no audio). Fallback chain: Cartesia -> OpenAI TTS -> macOS `say`.

### Circuit breaker tripped
Gemini had repeated failures. Auto-recovers in 60-120s with half-open probing. Claude fallback is active for scoring during this time.

### No audio/video from Zoom demo
BlackHole or OBS Virtual Camera is misconfigured. See [zoom-capture-setup.md](zoom-capture-setup.md) for full setup and troubleshooting. Quick checks: verify OBS Virtual Camera is started, re-run device discovery scripts, confirm `.env` indices match.

### Demo timer warning
At 90% of MAX_DEMO_DURATION (default 10 min), operator gets a warning. The timer does NOT auto-stop -- operator must click STOP manually.

### Long team names overflow the display
Team names are truncated with ellipsis on the audience display. Keep team names
under ~30 characters for best appearance on the projected screen.

## Quick-Reference: Failure → Recovery

| Symptom | Cause | Recovery |
|---------|-------|----------|
| Scores all 5.0 | All LLM providers failed | Use human scoring API to override |
| No audio from TTS | Cartesia down | Auto-fallback to OpenAI TTS → macOS `say` |
| "Circuit breaker tripped" | Gemini rate limit | Auto-recovers in 60-120s; Claude fallback active |
| Commentary empty | LLM streaming timeout | Partial text preserved; score reveal still fires |
| Buttons stuck disabled | Command timeout | Auto-clears after 10s; check WebSocket connection |
| Display frozen | WebSocket disconnect | Press backtick to open view switcher; audience auto-reconnects |
| No camera/audio | Wrong device index | Check `CAMERA_DEVICE_INDEX` / `AUDIO_DEVICE_INDEX` in `.env` |
| Score > 10.0 displayed | _(fixed)_ | Capped at 10.0 server-side since pre-event hardening |
| Team name looks weird | Newlines in name | Sanitized at input; max 60 chars enforced |
| Invalid track assigned | Typo in track name | Auto-defaults to ROGUE::AGENT with warning log |

## Emergency Procedures

### System crash mid-demo
1. Restart: `uv run arbiter`
2. Scores already saved to `data/scores/` -- they persist
3. Observations saved to `data/observations/`
4. Session checkpoint at `data/session_checkpoint.json` logs a warning on restart

### All LLM APIs down
1. Scoring uses 5.0 fallback (check justification text)
2. Commentary degrades to static text
3. Use human scoring API to enter real scores manually
4. Event continues -- no hard dependency on any single API

### Display frozen
1. Press backtick (`` ` ``) on audience display to open view switcher
2. Press number keys to force any screen state
3. View switcher auto-hides after 3 seconds

### Network drop during demo
1. Capture continues on the backend regardless of dashboard connection
2. Both dashboards auto-reconnect and resync state
3. No commands are lost -- if a command was in-flight, the 10s timeout
   triggers and you can retry
4. If the network is down for an extended period, the demo can still be
   stopped via the CLI backup: `uv run python -m src.operator.cli`

## Rehearsal Mode

Practice the full pipeline with synthetic data:

```bash
uv run arbiter --rehearsal
```

Or from the dashboard, use the "rehearsal" command button. Rehearsal runs defense -> commentary -> scoring -> deliberation with mocked data. Useful for timing validation and display verification.

## Configuration

Key environment variables (see `.env.example` for full list):

| Variable | Default | Purpose |
|----------|---------|---------|
| GEMINI_API_KEY | (required) | Primary LLM for capture + scoring |
| ANTHROPIC_API_KEY | (optional) | Claude fallback for scoring |
| CARTESIA_API_KEY | (optional) | TTS engine |
| CAMERA_DEVICE_INDEX | 0 | Camera device for capture |
| AUDIO_DEVICE_INDEX | 0 | Microphone for audio capture (see [zoom-capture-setup.md](zoom-capture-setup.md) for Zoom demos) |
| MAX_DEMO_DURATION | 600 | Max demo length in seconds |
| ARBITER_AI_WEIGHT | 0.7 | AI score weight in blended score |
| ARBITER_HUMAN_WEIGHT | 0.3 | Human score weight in blended score |
