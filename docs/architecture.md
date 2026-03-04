# Arbiter Architecture -- NEBULA:FOG 2026

## System Overview

Arbiter is a live AI judge agent for the NEBULA:FOG 2026 security hackathon. It captures
team demos via camera/audio, detects prompt injection attacks, generates real-time
commentary with TTS, scores demos with multi-model consensus, and orchestrates a theatrical
score reveal on the audience display.

```
                         NEBULA:FOG 2026 -- ARBITER SYSTEM
  ============================================================================

  +-----------------+       WebSocket /ws/operator        +------------------+
  |   OPERATOR      |<----------------------------------->|                  |
  |   DASHBOARD     |  commands (start/stop/pause/reset)  |                  |
  |   (React/TS)    |  state, counters, events, health    |                  |
  +-----------------+                                     |                  |
                                                          |   FASTAPI        |
  +-----------------+       WebSocket /ws/display          |   BACKEND        |
  |   AUDIENCE      |<----------------------------------->|   (Python)       |
  |   DISPLAY       |  commentary, scores, injection      |                  |
  |   (React/TS)    |  alerts, intermission, Q&A          |                  |
  +-----------------+                                     +--------+---------+
                                                                   |
                           +---------------------------------------+
                           |
            +--------------+--------------+-----------------+
            |              |              |                 |
       +----+----+   +----+----+   +-----+-----+   +------+------+
       | CAPTURE |   | DEFENSE |   | COMMENTARY|   |   SCORING   |
       | camera  |   | inject  |   | generator |   |   engine    |
       | audio   |   | detect  |   | TTS       |   |   MoE       |
       | OCR     |   | sanitize|   | streaming |   |   rubric    |
       +---------+   +---------+   +-----------+   +-------------+
            |              |              |                 |
            +--------------+--------------+-----------------+
                           |
                    +------+------+
                    |  EVENT BUS  |
                    |  (pub/sub)  |
                    +------+------+
                           |
         +-----------------+-----------------+
         |                 |                 |
    +----+----+     +------+------+   +------+------+
    | GEMINI  |     |   CLAUDE    |   |    GROQ     |
    | primary |     |  fallback   |   |  fallback   |
    +---------+     +-------------+   +-------------+
```

## Module Map

```
src/
  capture/           Camera, audio, OCR, Gemini Live session
    demo_machine.py     State machine (idle -> capturing -> paused -> stopped)
    event_bus.py        Pub/sub for CaptureEvents (asyncio.create_task dispatch)
    pipeline.py         Orchestrates capture -> observation flow
    gemini_session.py   Gemini Live API multimodal session

  defense/           Prompt injection detection + sanitization
    injection_detector.py   Pattern + LLM-based injection detection
    sanitizer.py            Scrubs detected injections from observations
    pipeline.py             Orchestrates detect -> sanitize flow
    roast_generator.py      Generates audience-facing roasts for blocked attacks

  commentary/        Real-time commentary + audience display
    generator.py        LLM commentary generation (Gemini -> Groq fallback)
    tts_engine.py       Text-to-speech (Cartesia -> OpenAI -> macOS say)
    display_server.py   FastAPI + WebSocket server for audience/operator
    pipeline.py         Orchestrates generate -> TTS -> display flow

  scoring/           Multi-model consensus scoring
    engine.py           Single-model scoring against rubric
    moe_engine.py       Mixture-of-Experts: multiple models vote + aggregate
    aggregator.py       Weighted average + confidence calibration
    pipeline.py         Orchestrates sanitize -> score -> reveal flow
    store.py            Persists scorecards to data/scores/

  operator/          Operator interface
    web.py              WebSocket command handler (WebOperator)
    cli.py              Terminal CLI (backup interface)
    audit.py            Command audit logging

  resilience/        Fault tolerance
    circuit_breaker.py  Half-open recovery for Gemini failures
    health.py           Service health aggregation
    metrics.py          Prometheus-compatible metrics
    retry.py            Exponential backoff retry wrapper

  memory/            Cross-demo deliberation
    pipeline.py         Final ranking across all scored teams
    deliberation_engine.py  LLM-powered comparative analysis

  providers/         LLM provider abstraction
    gemini_provider.py  Google Gemini
    claude_provider.py  Anthropic Claude
    groq_provider.py    Groq (Llama)
    openai_provider.py  OpenAI (TTS only)

  reports/           Post-event output
    card.py             HTML report card generation
    export.py           Full event data export

operator-dashboard/  React/TypeScript operator UI
  store/operatorStore.ts   Zustand state (demo state, counters, events)
  hooks/useOperatorSocket.ts  WebSocket connection + reconnect logic
  components/              NeuralPrompt, ReconnectBanner, Header, etc.
  panels/                  VitalsPanel, EventsPanel, HealthPanel, etc.

audience-display/    React/TypeScript audience projection UI
  store/displayStore.ts    Zustand state (screens, commentary, scores)
  hooks/useArbiterSocket.ts  WebSocket connection + reconnect logic
  screens/                 CommentaryScreen, ScoreCardScreen, etc.
  components/              Sigil (animated logo), CriterionRow, etc.
```

## Demo State Machine

The core lifecycle is a finite state machine managed by `DemoMachine`.

```
                     DEMO STATE MACHINE
  ========================================================

                   start_demo(team_name)
          +--------+---------------------->+-----------+
          |  IDLE  |                       | CAPTURING |
          +---+----+<------+               +-----+-----+
              ^    reset    |                 |       |
              |             |          pause  |       | stop
              |             |                 v       |
              |         +---+----+      +---------+   |
              |         | STOPPED|<-----| PAUSED  |   |
              |         +--------+ stop +----+----+   |
              |             ^                |        |
              |             |           resume|       |
              |             +----------------+        |
              |                                       |
              +---------------------------------------+
                            stop_demo
```

**State transitions and side effects:**

| Transition | Trigger | Side Effects |
|------------|---------|-------------|
| idle -> capturing | `start_demo` | Start timer, reset counters, push `capture_started` to audience |
| capturing -> paused | `pause_demo` | Timer continues, capture suspended |
| paused -> capturing | `resume_demo` | Capture resumes |
| capturing/paused -> stopped | `stop_demo` | Cancel timer, trigger defense + scoring + commentary pipelines |
| stopped -> idle | `reset` | Delete checkpoint, push intermission leaderboard |

## WebSocket Protocol

### Operator WebSocket (`/ws/operator`)

```
  OPERATOR DASHBOARD                          BACKEND (WebOperator)
  ==================                          ====================

  --- Connection Setup ---

  [connect] --------------------------------> [accept, add to connections]
                                              [push state + health + scoring_phase]
  {"type":"command","action":"get_state"} ---> [push state (redundant safety net)]

  --- Command Flow ---

  {"type":"command","action":"start",   ----> [validate, transition state machine]
   "team_name":"Alpha","track":"ROGUE::AGENT"}
                                        <---- {"type":"command_result",
                                               "success":true,
                                               "message":"Demo started for Alpha"}
                                        <---- {"type":"state","state":"capturing",
                                               "team_name":"Alpha",...}

  --- Continuous Streaming (1s interval) ---

                                        <---- {"type":"counters","frames":42,...}
                                        <---- {"type":"health","services":{...}}

  --- Event Streaming (as they occur) ---

                                        <---- {"type":"event",
                                               "event_type":"injection_detected",...}

  --- Heartbeat ---

                                        <---- {"type":"ping"}
  {"type":"pong"} ---------------------->

  --- Timer Warning ---

                                        <---- {"type":"demo_timer","level":"warning",
                                               "message":"90s remaining",...}

  --- Scoring Phase Tracking ---

                                        <---- {"type":"scoring_phase",
                                               "phase":"sanitizing"}
                                        <---- {"type":"scoring_phase",
                                               "phase":"scoring"}
                                        <---- {"type":"scoring_phase",
                                               "phase":"revealing"}
```

### Audience Display WebSocket (`/ws/display`)

```
  AUDIENCE DISPLAY                            BACKEND (DisplayServer)
  ================                            ======================

  [connect] --------------------------------> [accept, replay cached screen state]
  {"type":"request_state"} ----------------->  [replay cached state (safety net)]

  --- Screen Updates (server-push only) ---

                                        <---- {"type":"capture_started",
                                               "team_name":"Alpha","track":"..."}
                                        <---- {"type":"commentary",
                                               "sentences":[...]}
                                        <---- {"type":"injection_blocked",
                                               "category":"...","roast":"..."}
                                        <---- {"type":"score_intro",...}
                                        <---- {"type":"score_criterion",...}
                                        <---- {"type":"intermission",
                                               "leaderboard":[...],...}
                                        <---- {"type":"question",...}

  --- Heartbeat ---

                                        <---- {"type":"ping"}
  "pong" -------------------------------->
```

## Command Lifecycle with Timeout

The operator dashboard tracks pending commands to prevent button lockup
if the server never responds (e.g., WebSocket message lost).

```
  COMMAND LIFECYCLE (pendingCommand + timeout)
  ============================================

       User clicks button
              |
              v
  +------------------------+
  | set pendingCommand =   |    Buttons become disabled,
  | action name            |    active button shows spinner
  | start 10s timeout      |
  +------------------------+
              |
     +--------+--------+
     |                  |
     v                  v
  Server responds    10s timeout fires
  (command_result)   (no response)
     |                  |
     v                  v
  +----------------+ +---------------------------+
  | clear pending  | | clear pendingCommand      |
  | clear timeout  | | set lastCommandResult =   |
  | show result    | |   "Command timed out"     |
  +----------------+ +---------------------------+
     |                  |
     v                  v
  Buttons re-enabled    Buttons re-enabled
  (3s auto-clear msg)   (3s auto-clear error msg)
```

## WebSocket Reconnect Flow

Both frontends auto-reconnect with exponential backoff. State resync
ensures the UI is never stale after a network drop.

```
  RECONNECT FLOW (both dashboards)
  ================================

  [connected] ----network drop----> [close fires]
                                        |
                                        v
                                  [set disconnected]
                                  [show banner:
                                   "CONNECTION LOST --
                                    RECONNECTING..."]
                                        |
                                        v
                                  [wait backoff]
                                  [1s -> 2s -> 4s -> 8s -> 10s max]
                                        |
                                        v
                                  [new WebSocket()]
                                        |
                                  +-----+------+
                                  |            |
                                  v            v
                              [onopen]     [onerror]
                                  |            |
                                  v            v
                          [set connected]  [close -> retry]
                          [hide banner]
                          [send resync:
                           get_state (operator)
                           request_state (audience)]
                                  |
                                  v
                          [server pushes full
                           current state]
                                  |
                                  v
                          [UI fully current]
```

## Disconnected Command Handling

When the operator sends a command while disconnected, the UI surfaces
the error immediately instead of silently dropping it.

```
  DISCONNECTED COMMAND HANDLING
  =============================

  User clicks STOP
       |
       v
  wsRef.readyState !== OPEN?
       |
       +-- YES --> dispatch synthetic command_result:
       |           {success: false, message: "Not connected"}
       |           |
       |           v
       |           Error toast shown for 3s
       |           pendingCommand NOT set (button stays enabled)
       |
       +-- NO ---> normal flow (send JSON, set pendingCommand)
```

## Fallback Chains

Arbiter degrades gracefully when services fail. Every critical path
has at least one fallback.

```
  FALLBACK CHAINS
  ===============

  Scoring:       Gemini ──fail──> Claude ──fail──> 5.0 fallback scorecard
                   |                |                    |
                   v                v                    v
               Primary MoE    Single-model          Static scores
               (3 Gemini +    scoring with          "manual review
                1 Claude)     same rubric           required"

  Commentary:    Gemini ──fail──> Groq ──fail──> Static text
                   |                |                |
                   v                v                v
               Streaming        Streaming         Pre-written
               sentences        sentences         fallback

  TTS:         Cartesia ──fail──> OpenAI ──fail──> macOS `say`
                   |                 |                  |
                   v                 v                  v
               Low-latency      Standard API      System speech
               streaming        batch TTS         synthesis

  Circuit Breaker (Gemini):
                 CLOSED ──failures──> OPEN ──60s──> HALF-OPEN
                   ^                                    |
                   |              probe succeeds        |
                   +------------------------------------+
                                      |
                              probe fails: OPEN (120s)
```

## Frontend Component Tree

### Operator Dashboard

```
  App
   +-- Header (connection dot, demo state badge)
   +-- ReconnectBanner (shown when connecting OR reconnecting)
   +-- main layout (CSS grid)
   |    +-- VitalsPanel
   |    |    +-- StateIndicator (colored dot)
   |    |    +-- Timer ("--:--" idle, green when capturing, frozen when stopped)
   |    |    +-- CounterBar x3 (Frames, Audio, Threats)
   |    |    +-- Shield percentage
   |    |    +-- Sparkline (event rate)
   |    +-- EventsPanel (scrolling event log)
   |    +-- HealthPanel (service status grid)
   |    +-- ScorePanel (scorecard + scoring phase indicator)
   +-- NeuralPrompt (command bar)
        +-- team name input + track dropdown (idle only)
        +-- action buttons with loading spinner
        +-- shortcut hints
        +-- deliberation confirmation modal
```

### Audience Display

```
  App
   +-- ArbiterSigil (animated SVG background, emotion-driven)
   +-- screen router (based on displayStore.currentScreen)
        +-- IdleScreen (logo + event name)
        +-- CaptureScreen (team name + track, "analyzing...")
        +-- CommentaryScreen (streaming sentences with emotion colors)
        +-- ThinkingScreen (arbiter is processing)
        +-- ScoreCardScreen (criterion-by-criterion reveal)
        +-- QuestionScreen (Q&A for the team)
        +-- IntermissionScreen (leaderboard between demos)
        +-- DeliberationScreen (final rankings + narrative)
        +-- InjectionBlockedScreen (attack detected overlay)
```

## Data Flow: Full Demo Lifecycle

```
  FULL DEMO LIFECYCLE
  ===================

  1. IDLE
     Operator enters team name, selects track
     Audience sees: IdleScreen or IntermissionScreen

  2. START (operator clicks START)
     DemoMachine: idle -> capturing
     Camera + audio capture begins via Gemini Live API
     Audience sees: CaptureScreen ("analyzing Team Alpha...")
     Operator sees: counters ticking, events streaming

  3. CAPTURING (3-10 minutes)
     Gemini processes video frames + audio in real-time
     Key frames extracted, transcripts generated
     Injection detector runs on every observation
     Blocked attacks -> InjectionBlockedScreen + roast
     Clean observations -> stored for scoring

  4. STOP (operator clicks STOP)
     DemoMachine: capturing -> stopped
     Three parallel pipelines launch:

     a) Defense Pipeline (~2s)
        Sanitize all observations, remove injection residue

     b) Commentary Pipeline (~10-20s)
        LLM generates streaming sentences
        Each sentence -> TTS -> audio playback
        Each sentence -> audience display (emotion-colored)
        Audience sees: CommentaryScreen

     c) Scoring Pipeline (~5-15s, parallel with commentary)
        MoE engine: 3 Gemini + 1 Claude score independently
        Aggregator: weighted average with confidence calibration
        Store scorecard to data/scores/

  5. SCORE REVEAL (after commentary finishes)
     Theatrical sequence:
       score_intro -> ThinkingScreen (2s)
       score_criterion x N -> ScoreCardScreen (one by one)
       total score reveal -> ScoreCardScreen (final)
     Audience sees: ScoreCardScreen

  6. Q&A (optional, operator clicks Q&A)
     LLM generates targeted questions for the team
     Audience sees: QuestionScreen

  7. RESET (operator clicks NEXT TEAM)
     DemoMachine: stopped -> idle
     Leaderboard computed from all scores
     Audience sees: IntermissionScreen
     Loop back to step 1

  8. DELIBERATION (after all demos)
     Cross-demo comparative analysis
     Reverse-order reveal (worst to best)
     Winner gets gold treatment
     Audience sees: DeliberationScreen
```
