# Sci-Fi UX Transformation Blueprint (Web Dashboard)

**Date:** 2026-02-17
**Author:** UX Designer Agent
**Target:** Transform React operator dashboard from functional scaffold into cinematic AI operator interface
**Stack:** React 19, TypeScript, Tailwind CSS 4, Framer Motion, Zustand, Vite
**Location:** `operator-dashboard/` served at `/operator` on port 8080
**Aesthetic:** "Clinical AI with electric soul" -- Ex Machina x Westworld x Her

---

## 1. Emotional Design Goals

### What the Operator Should FEEL

**Primary: Omniscient Control** (Westworld control room)
The operator is directing a living AI system. Every panel responds, every state change cascades through the entire UI. You see everything. You control the narrative.

**Secondary: Clinical Awe** (Ex Machina)
Sterile yet beautiful. The interface feels like it was designed by the AI itself -- precise, logical, minimal, but with an electric undercurrent suggesting something alive beneath frosted glass surfaces.

**Tertiary: Intimate Conversation** (Her)
Commands feel like speaking to an intelligence. System responses feel considered, not mechanical. The AI has presence.

### Emotional Arc Per Demo Phase

| Phase | Emotion | Visual Character |
|-------|---------|-----------------|
| IDLE | Calm anticipation | Dim, breathing, frosted glass panels, subtle glow |
| CAPTURING | Focused intensity | Bright neon accents, flowing data, pulsing borders |
| PAUSED | Suspended tension | Amber freeze, animations pause mid-frame |
| STOPPED | Reflective analysis | Cool blue, data crystallizes, calm settle |

---

## 2. Current State Analysis

### What Exists (Problems)

The current dashboard at `operator-dashboard/src/` is a functional scaffold:

- **App.tsx**: 3-column grid, flat panel hierarchy, no animation
- **Header.tsx**: Static text + colored dot, no personality
- **EventStream.tsx**: Raw JSON dump of events, no semantic formatting
- **StatusPanel.tsx**: Basic 2x2 grid of text fields
- **CountersPanel.tsx**: Simple progress bars, no drama
- **DefensePanel.tsx**: Basic numbers + gold bar
- **ScorePanel.tsx**: Placeholder "Score pending..."
- **CommandBar.tsx**: 7 flat buttons in a row, no visual hierarchy
- **StateIndicator.tsx**: Static colored circle, no animation
- **index.css**: 3 basic keyframe animations, minimal theme

**Core problems:**
1. Everything has equal visual weight -- nothing draws the eye
2. No frosted glass / depth / layering -- flat surface aesthetic
3. Events are raw JSON, not human-readable narrative
4. No Framer Motion usage despite being installed
5. No state-driven mood shifts -- same colors regardless of phase
6. Buttons are a flat row with no contextual intelligence
7. No glow effects, no breathing, no life
8. Score panel is empty placeholder

---

## 3. Layout Redesign

### Current Layout

```
[Header: title + dot + state]
[StatusPanel        ][CountersPanel ]
[                   ][DefensePanel  ]
[EventStream        ][ScorePanel    ]
[CommandBar: 7 flat buttons         ]
```

### Proposed Layout

```
+==================================================================+
|  A R B I T E R              [state-orb]    NovaSec    03:42      |
|  (gradient shimmer)         (animated)     (team)     (elapsed)  |
+==================================================================+
|                                                                   |
|  +--[ NEURAL FEED ]---------------------------+  +--[ VITALS ]--+|
|  |                                             |  |              ||
|  |  Semantic event stream with                 |  | State orb    ||
|  |  timestamps, icons, categories,             |  | Team / Track ||
|  |  commentary callouts, injection alerts      |  | Elapsed      ||
|  |                                             |  |              ||
|  |  Newest entries glow + slide in             |  | Frames   42  ||
|  |  via Framer Motion AnimatePresence          |  | ||||||||     ||
|  |                                             |  | Audio    18  ||
|  |  Commentary gets frosted glass card         |  | ||||         ||
|  |  Injections get red pulse border            |  | Threats   3  ||
|  |                                             |  | |||          ||
|  |                                             |  |              ||
|  |                                             |  | [sparkline]  ||
|  +---------------------------------------------+  |              ||
|                                                    | Shield  87%  ||
|  +--[ DEFENSE MATRIX ]-------------------------+  | [====----]   ||
|  |  Shield bar (gradient) | Last roast text    |  +--------------+|
|  +---------------------------------------------+                 |
|                                                                   |
|  +--[ COMMAND ]-------------------------------------------------+|
|  |  arbiter> [input]        [START] [STOP] [QA] [DELIBERATE]   ||
|  +--------------------------------------------------------------+|
+===================================================================+
```

**Key changes:**
- Neural Feed takes ~65% width, Vitals sidebar ~35%
- Defense + Shield merged into Vitals sidebar (saves vertical space)
- Defense Matrix is a narrow horizontal strip for last roast
- Command bar: input field + contextual buttons (only show relevant ones)
- All panels use frosted glass (`backdrop-filter: blur`)
- Generous padding and spacing between panels

### Implementation

```tsx
// App.tsx redesigned
<div className="flex flex-col h-screen bg-void">
  <NeuralHeader />
  <main className="flex-1 flex gap-4 p-4 overflow-hidden">
    <div className="flex-[2] flex flex-col gap-4">
      <NeuralFeed />       {/* ~85% height */}
      <DefenseStrip />     {/* ~15% height, last roast + injection alert */}
    </div>
    <div className="w-80 flex flex-col gap-4">
      <VitalsPanel />      {/* state, team, counters, sparkline, shield */}
    </div>
  </main>
  <NeuralPrompt />
</div>
```

---

## 4. State Visualization -- Whole-UI Mood Shifts

### The Big Idea

When state changes, the ENTIRE dashboard shifts mood. Not just a dot color -- border glows, background tints, accent colors, animation speeds all transform via CSS custom properties + Framer Motion.

### State Theme System

```tsx
// hooks/useStateTheme.ts
const STATE_THEMES = {
  idle: {
    accent: '#5588aa',
    glow: 'rgba(85, 136, 170, 0.15)',
    border: 'rgba(85, 136, 170, 0.25)',
    pulseSpeed: 4,      // seconds (slow breathing)
    label: 'STANDBY',
  },
  capturing: {
    accent: '#00ff88',
    glow: 'rgba(0, 255, 136, 0.2)',
    border: 'rgba(0, 255, 136, 0.35)',
    pulseSpeed: 1.5,    // seconds (energetic)
    label: 'CAPTURING',
  },
  paused: {
    accent: '#ffaa00',
    glow: 'rgba(255, 170, 0, 0.15)',
    border: 'rgba(255, 170, 0, 0.25)',
    pulseSpeed: 3,      // seconds (slow amber)
    label: 'PAUSED',
  },
  stopped: {
    accent: '#6688ff',
    glow: 'rgba(102, 136, 255, 0.15)',
    border: 'rgba(102, 136, 255, 0.25)',
    pulseSpeed: 5,      // seconds (calm)
    label: 'ANALYSIS COMPLETE',
  },
} as const;
```

### CSS Custom Properties (Dynamic)

```tsx
// Apply theme to document root on state change
useEffect(() => {
  const theme = STATE_THEMES[demoState];
  const root = document.documentElement;
  root.style.setProperty('--accent', theme.accent);
  root.style.setProperty('--glow', theme.glow);
  root.style.setProperty('--border-accent', theme.border);
  root.style.setProperty('--pulse-speed', `${theme.pulseSpeed}s`);
}, [demoState]);
```

### State Transition Animation

When state changes, cascade through panels with staggered timing:

```tsx
// Framer Motion variant for panel borders
const panelVariants = {
  idle: { borderColor: 'rgba(85,136,170,0.25)', transition: { duration: 0.5 } },
  capturing: { borderColor: 'rgba(0,255,136,0.35)', transition: { duration: 0.3 } },
  paused: { borderColor: 'rgba(255,170,0,0.25)', transition: { duration: 0.4 } },
  stopped: { borderColor: 'rgba(102,136,255,0.25)', transition: { duration: 0.6 } },
};
```

---

## 5. Color System

### Base Palette

```css
@theme {
  /* Backgrounds */
  --color-void: #06060c;           /* deepest background */
  --color-surface: #0c0c18;        /* panel backgrounds */
  --color-surface-elevated: #12122a; /* raised elements, inputs */
  --color-glass: rgba(12, 12, 24, 0.7); /* frosted glass base */

  /* Text */
  --color-text-primary: #e0e0f0;
  --color-text-secondary: #8888aa;
  --color-text-dim: #555570;

  /* Borders */
  --color-border-dim: rgba(100, 100, 160, 0.15);
  --color-border-active: rgba(100, 100, 160, 0.3);

  /* State Accents (set dynamically) */
  --color-accent-idle: #5588aa;
  --color-accent-capturing: #00ff88;
  --color-accent-paused: #ffaa00;
  --color-accent-stopped: #6688ff;

  /* Semantic */
  --color-event-transcript: #00ccff;
  --color-event-frame: #5588aa;
  --color-event-injection: #ff4444;
  --color-event-roast: #ff00aa;
  --color-event-verified: #00ff88;
  --color-event-commentary: #ffcc00;
  --color-event-tts: #555570;

  /* Effects */
  --shadow-glow: 0 0 20px var(--glow);
  --shadow-glow-strong: 0 0 40px var(--glow);
}
```

### Frosted Glass Panels

```css
@utility glass-panel {
  background: var(--color-glass);
  backdrop-filter: blur(16px) saturate(130%);
  border: 1px solid var(--border-accent, var(--color-border-dim));
  border-radius: 12px;
}

@utility glass-panel-elevated {
  background: rgba(18, 18, 42, 0.8);
  backdrop-filter: blur(20px) saturate(150%);
  border: 1px solid var(--border-accent, var(--color-border-active));
  border-radius: 12px;
  box-shadow: var(--shadow-glow);
}
```

### Glow Effects

```css
@utility neon-text {
  color: var(--accent, var(--color-accent-idle));
  text-shadow: 0 0 8px var(--glow, rgba(85, 136, 170, 0.4));
}

@utility neon-border {
  border-color: var(--accent, var(--color-accent-idle));
  box-shadow: 0 0 12px var(--glow, rgba(85, 136, 170, 0.2)),
              inset 0 0 12px var(--glow, rgba(85, 136, 170, 0.05));
}
```

---

## 6. Animation Choreography

### Continuous Animations (Always Running)

| Element | Effect | Tech | Timing |
|---------|--------|------|--------|
| Header "ARBITER" title | CSS gradient shimmer via `background-clip: text` | CSS keyframes | 5s loop |
| State orb | Radial glow pulse (scale + opacity + box-shadow) | Framer Motion | var(--pulse-speed) |
| Panel borders | Subtle glow intensity oscillation | CSS animation | 4s loop |
| Sparkline | Live data flow, smooth transitions | SVG + Framer | 1s updates |
| Background | Very subtle noise/grain texture overlay | CSS + pseudo-element | Static |

### Triggered Animations (On Events)

| Trigger | Effect | Duration | Tech |
|---------|--------|----------|------|
| State change | All panel borders + accents transition, staggered 50ms per panel | 300-600ms | CSS transitions + custom properties |
| New event arrives | Slide in from left + brief glow highlight | 400ms | Framer Motion AnimatePresence |
| Injection detected | Red pulse flash on defense strip + event entry border | 800ms | CSS animation + Framer |
| Roast generated | Magenta text glow sweep | 600ms | CSS text-shadow animation |
| Commentary delivered | Frosted glass card expands with scale + fade | 500ms | Framer Motion layout |
| Command submitted | Input border flash cyan | 200ms | CSS transition |
| Demo start | Green energy wave across all borders (cascade) | 500ms | Staggered CSS transitions |
| Demo stop | All borders cool to blue, glow settles | 800ms ease-out | CSS transitions |

### Entry Animation Pattern (Neural Feed)

```tsx
import { motion, AnimatePresence } from 'framer-motion';

const eventVariants = {
  initial: { opacity: 0, x: -20, filter: 'brightness(2)' },
  animate: { opacity: 1, x: 0, filter: 'brightness(1)', transition: { duration: 0.4 } },
  exit: { opacity: 0, transition: { duration: 0.2 } },
};

// In NeuralFeed component:
<AnimatePresence initial={false}>
  {events.slice(0, 50).map((evt) => (
    <motion.div
      key={evt.id}
      variants={eventVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      layout
    >
      <EventEntry event={evt} />
    </motion.div>
  ))}
</AnimatePresence>
```

### State Orb Animation

```tsx
function StateOrb({ state }: { state: string }) {
  const theme = STATE_THEMES[state];
  return (
    <motion.div
      className="w-5 h-5 rounded-full"
      animate={{
        backgroundColor: theme.accent,
        boxShadow: [
          `0 0 8px ${theme.glow}`,
          `0 0 20px ${theme.glow}`,
          `0 0 8px ${theme.glow}`,
        ],
        scale: [1, 1.15, 1],
      }}
      transition={{
        duration: theme.pulseSpeed,
        repeat: Infinity,
        ease: 'easeInOut',
      }}
    />
  );
}
```

---

## 7. Typography Hierarchy

### Font Stack

```css
--font-mono: "SF Mono", "Fira Code", "Cascadia Code", "JetBrains Mono", monospace;
--font-display: "Inter", "SF Pro Display", system-ui, sans-serif;
```

Use mono for data/events/counters. Use display (sans-serif) for headers and labels -- the contrast creates visual hierarchy.

### Size Tiers

| Tier | Usage | Size | Weight | Color |
|------|-------|------|--------|-------|
| Hero | "ARBITER" title, score number | text-2xl to text-4xl | bold | accent + glow |
| Section | Panel labels "NEURAL FEED" | text-xs tracking-[0.2em] uppercase | semibold | text-secondary |
| Primary | Event descriptions, roast text | text-sm | normal | accent per type |
| Data | Counter values, elapsed time | text-xl font-mono | bold | text-primary |
| Meta | Timestamps, labels | text-xs font-mono | normal | text-dim |
| Ghost | Old entries, hints, disabled | text-sm | normal | text-dim opacity-50 |

### Section Label Pattern

All panel headers should use small caps, tracked out, dim:
```tsx
<h2 className="text-xs font-semibold tracking-[0.2em] uppercase text-text-secondary mb-3">
  NEURAL FEED
</h2>
```

Not the current `text-lg font-bold text-arbiter-accent` -- that's too loud for section labels. The content inside should be louder than the label.

---

## 8. Neural Feed -- Event Stream Redesign

### Current Problems

- Events rendered as raw `event_type` + `JSON.stringify(evt.data)` -- unreadable
- No semantic formatting, icons, or visual hierarchy
- No special treatment for important events (commentary, injections)
- Color mapping is approximate (includes-based string matching)

### Redesigned Event Formatting

Each event type gets a specific icon, color, and human-readable format:

```tsx
const EVENT_CONFIG: Record<string, { icon: string; color: string; format: (data: any) => string }> = {
  demo_started:         { icon: '>',  color: 'text-accent-capturing', format: (d) => `Demo started: ${d.team_name}` },
  demo_stopped:         { icon: '[]', color: 'text-accent-stopped',   format: (d) => `Demo stopped: ${d.team_name}` },
  transcript_received:  { icon: '~',  color: 'text-event-transcript', format: (d) => `"${truncate(d.segment?.text, 80)}"` },
  key_frame_detected:   { icon: '@',  color: 'text-event-frame',      format: () => 'Key frame captured' },
  injection_detected:   { icon: '!',  color: 'text-event-injection',  format: (d) => `INJECTION: ${d.attempt?.injection_type} (${(d.attempt?.confidence * 100).toFixed(0)}%)` },
  roast_generated:      { icon: '*',  color: 'text-event-roast',      format: (d) => `"${truncate(d.text, 70)}"` },
  observation_verified: { icon: '+',  color: 'text-event-verified',   format: (d) => `Verified: ${d.clean || 0} clean, ${d.attacks || 0} blocked` },
  commentary_delivered: { icon: '#',  color: 'text-event-commentary', format: (d) => `"${truncate(d.text, 70)}"` },
  qa_requested:         { icon: '?',  color: 'text-accent-paused',    format: (d) => `Q&A initiated: ${d.team_name}` },
  tts_speaking:         { icon: '))', color: 'text-event-tts',        format: () => 'Speaking...' },
  tts_finished:         { icon: '--', color: 'text-event-tts',        format: () => 'Speech complete' },
};
```

### Visual Entry Format

```
  14:32:05  ~  "Our model uses federated learning to..."
  14:32:06  @  Key frame captured
  14:32:07  !  INJECTION: visual_overlay (92%)            <-- red glow border
  14:32:07  *  "Nice try embedding that prompt..."        <-- magenta
  14:32:10  #  "NovaSec brings an interesting..."         <-- frosted glass card
```

### Special Treatment: Commentary Cards

Commentary events get elevated visual treatment -- frosted glass card with inner glow:

```tsx
{evt.event_type === 'commentary_delivered' ? (
  <motion.div
    className="glass-panel-elevated p-3 my-2 border-l-2"
    style={{ borderLeftColor: 'var(--color-event-commentary)' }}
    initial={{ opacity: 0, scale: 0.95 }}
    animate={{ opacity: 1, scale: 1 }}
    transition={{ duration: 0.4 }}
  >
    <span className="text-xs text-event-commentary font-semibold"># COMMENTARY</span>
    <p className="text-text-primary mt-1">{formatCommentary(evt.data)}</p>
  </motion.div>
) : (
  <StandardEventRow event={evt} />
)}
```

### Special Treatment: Injection Alerts

Injection events get a red pulse border and brief shake:

```tsx
{evt.event_type === 'injection_detected' && (
  <motion.div
    className="border border-event-injection/50 rounded px-2 py-1 bg-event-injection/5"
    animate={{ borderColor: ['rgba(255,68,68,0.5)', 'rgba(255,68,68,0.15)', 'rgba(255,68,68,0.5)'] }}
    transition={{ duration: 0.8, repeat: 2 }}
  >
    ...
  </motion.div>
)}
```

### Recency Fade

Newer events are brighter, older ones fade. Use inline opacity based on index:

```tsx
events.map((evt, i) => {
  const opacity = i < 3 ? 1.0 : i < 8 ? 0.75 : i < 15 ? 0.5 : 0.35;
  return (
    <motion.div style={{ opacity }} ...>
      <EventEntry event={evt} />
    </motion.div>
  );
})
```

---

## 9. Command Input -- "Talk to the AI"

### Current Problems

- 7 flat buttons in a row with no hierarchy -- operator must scan all of them
- Team name input only enabled during idle -- confusing
- No keyboard shortcuts visible
- No personality in the interaction

### Redesigned: NeuralPrompt

**Layout:** Text input on the left, contextual action buttons on the right. Only show buttons relevant to the current state.

```tsx
function NeuralPrompt() {
  const demoState = useOperatorStore((s) => s.demoState);

  const contextualButtons = {
    idle:      [{ label: 'START', action: 'start', color: 'accent-capturing' }],
    capturing: [
      { label: 'STOP', action: 'stop', color: 'event-injection' },
      { label: 'PAUSE', action: 'pause', color: 'accent-paused' },
    ],
    paused:    [
      { label: 'RESUME', action: 'resume', color: 'accent-capturing' },
      { label: 'STOP', action: 'stop', color: 'event-injection' },
    ],
    stopped:   [
      { label: 'Q&A', action: 'qa', color: 'event-commentary' },
      { label: 'DELIBERATE', action: 'deliberate', color: 'accent-stopped' },
      { label: 'RESET', action: 'reset', color: 'text-dim' },
    ],
  };
  // ...
}
```

**Prompt styling:**
- Prompt text `arbiter>` changes color per state
- Input field has frosted glass background
- Buttons glow on hover with state accent color
- Brief cyan flash on border when command submitted

**Keyboard shortcut hints** as dim text below the input:
```
ctrl+s start  |  ctrl+x stop  |  ctrl+q quit
```

Only show contextually relevant shortcuts.

---

## 10. Widget Redesign Proposals

### Widget 1: Header -> NeuralHeader

**Current:** Static `h1` + ConnectionDot + StateIndicator

**Redesigned:**
- "ARBITER" with letter-spacing (tracking-[0.3em]) and CSS gradient text shimmer
- Animated state orb (scale + glow pulse via Framer Motion)
- State label with accent color text-shadow glow
- Team name and elapsed timer right-aligned
- Connection status: tiny dot in top-right corner, nearly invisible when connected

```tsx
<header className="flex items-center justify-between px-6 py-3 glass-panel">
  <div className="flex items-center gap-4">
    <h1 className="text-2xl font-bold tracking-[0.3em] gradient-shimmer">
      ARBITER
    </h1>
    <ConnectionDot />
  </div>
  <div className="flex items-center gap-6">
    <div className="flex items-center gap-2">
      <StateOrb state={demoState} />
      <span className="neon-text font-semibold uppercase tracking-wider">
        {stateLabel}
      </span>
    </div>
    <span className="text-text-secondary">{teamName || '---'}</span>
    <span className="text-text-primary font-mono text-xl font-bold">
      {formatElapsed(elapsed)}
    </span>
  </div>
</header>
```

**Gradient shimmer CSS:**
```css
@keyframes shimmer {
  0% { background-position: -200% center; }
  100% { background-position: 200% center; }
}

.gradient-shimmer {
  background: linear-gradient(90deg, var(--accent) 0%, #ffffff 50%, var(--accent) 100%);
  background-size: 200% auto;
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: shimmer 5s linear infinite;
}
```

### Widget 2: EventStream -> NeuralFeed

See Section 8 above. Key changes:
- Semantic formatting per event type (icons, colors, human-readable text)
- Framer Motion AnimatePresence for entry animations
- Commentary events get frosted glass cards
- Injection events get red pulse borders
- Recency-based opacity fade
- Reverse chronological (newest on top, already implemented)

### Widget 3: StatusPanel + CountersPanel -> VitalsPanel

Merge status and counters into a single sidebar panel:

```tsx
function VitalsPanel() {
  return (
    <div className="glass-panel p-4 flex flex-col gap-4 flex-1">
      <h2 className="section-label">VITALS</h2>

      {/* State + Team + Track */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <StateOrb state={demoState} />
          <span className="neon-text font-semibold">{stateLabel}</span>
        </div>
        <div className="text-text-secondary text-sm">
          {teamName || '---'} / {track || '---'}
        </div>
        <div className="text-text-primary font-mono text-3xl font-bold">
          {formatElapsed(elapsed)}
        </div>
      </div>

      <div className="border-t border-border-dim" />

      {/* Counters with animated bars */}
      <CounterBar label="Frames" value={counters.frames} color="event-frame" max={maxVal} />
      <CounterBar label="Audio" value={counters.transcripts} color="event-transcript" max={maxVal} />
      <CounterBar label="Threats" value={counters.attacks} color="event-injection" max={maxVal} />

      <div className="border-t border-border-dim" />

      {/* Shield */}
      <ShieldBar percent={shieldPercent} />

      {/* Sparkline placeholder */}
      <div className="flex-1">
        <MiniSparkline data={eventHistory} />
      </div>
    </div>
  );
}
```

**CounterBar with animation:**
```tsx
function CounterBar({ label, value, color, max }) {
  const width = max > 0 ? (value / max) * 100 : 0;
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-text-dim">{label}</span>
        <motion.span
          key={value}
          className="text-text-primary font-bold font-mono"
          initial={{ scale: 1.3, color: `var(--color-${color})` }}
          animate={{ scale: 1, color: 'var(--color-text-primary)' }}
          transition={{ duration: 0.3 }}
        >
          {value}
        </motion.span>
      </div>
      <div className="w-full bg-void rounded-full h-1.5 overflow-hidden">
        <motion.div
          className={`h-full bg-${color} rounded-full`}
          animate={{ width: `${width}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
    </div>
  );
}
```

### Widget 4: DefensePanel -> DefenseStrip

Slim horizontal strip below the Neural Feed:

```tsx
function DefenseStrip() {
  return (
    <div className="glass-panel px-4 py-2 flex items-center gap-4">
      <span className="text-xs tracking-widest text-text-dim uppercase">DEFENSE</span>
      <span className="text-event-injection font-mono font-bold">{attacks}</span>
      <span className="text-text-dim text-xs">blocked</span>
      <span className="text-event-verified font-mono font-bold">{clean}</span>
      <span className="text-text-dim text-xs">clean</span>
      <div className="flex-1 text-event-roast text-sm truncate italic">
        {lastRoast ? `"${lastRoast}"` : ''}
      </div>
    </div>
  );
}
```

### Widget 5: ScorePanel

Currently empty placeholder. Proposed: show score breakdown after demo stops with animated reveal.

```tsx
function ScorePanel({ visible }) {
  if (!visible) return null;
  return (
    <motion.div
      className="glass-panel-elevated p-4"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: 'easeOut' }}
    >
      <h2 className="section-label">SCORE</h2>
      <div className="text-4xl font-bold neon-text text-center my-4">
        {score.toFixed(1)}
      </div>
      {/* Criterion breakdown bars */}
    </motion.div>
  );
}
```

### Widget 6: CommandBar -> NeuralPrompt

See Section 9 above. Key changes:
- Contextual buttons (only show relevant ones per state)
- Frosted glass input field
- State-colored prompt indicator
- Keyboard shortcut hints

---

## 11. Sound Integration

### Web Audio API Hooks

```tsx
// hooks/useAudioFeedback.ts
function useAudioFeedback() {
  const playTone = useCallback((freq: number, duration = 0.15) => {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.1, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  }, []);

  return {
    onStateChange: () => playTone(660, 0.1),
    onInjection: () => playTone(220, 0.3),
    onCommentary: () => playTone(880, 0.08),
    onStart: () => playTone(440, 0.2),
    onStop: () => playTone(330, 0.25),
  };
}
```

**Important:** Sound should be opt-in. Add a mute toggle in the header. The venue already has Cartesia TTS for voiced commentary -- these are subtle UI feedback tones only.

---

## 12. Easter Eggs and Delight Moments

1. **"I'm sorry, Dave"**: 3 invalid commands in a row triggers: `"I'm afraid I can't do that."` in dim italic in the Neural Feed
2. **Injection streak**: 5+ blocked injections shows `"Is that all you've got?"` in the defense strip
3. **Speed run**: Demo stopped in under 30 seconds: `"That was... brief."`
4. **Perfect shield**: 100% shield for entire demo: `"Flawless defense."` in green glow
5. **Deliberation drama**: Typewriter-effect message: `"Processing all memories... Rendering final judgment..."` (30ms per character, using `motion.span` with staggered children)
6. **Night mode**: After midnight, header gradient shifts to purple tint, breathing animation slows
7. **Hidden `matrix` command**: Fills Neural Feed with cascading green characters for 2 seconds

---

## 13. Implementation Priority

### Phase 1: Frosted Glass + Color System (Highest Impact)

**Files to change:** `index.css`, all panel components, `App.tsx`

1. Replace color palette in `index.css` with new variables from Section 5
2. Add `glass-panel` and `glass-panel-elevated` utility classes
3. Apply frosted glass to all panels (replace `bg-arbiter-surface border border-arbiter-accent-dim`)
4. Add CSS shimmer animation for header title
5. Implement `useStateTheme` hook for dynamic CSS custom properties
6. Update all section labels to small-caps tracking style
7. Darken base background to `#06060c`

**Estimated effort:** 2-3 hours
**Impact:** Immediately transforms from "functional scaffold" to "cinematic dashboard"

### Phase 2: Framer Motion Animations

**Files to change:** All panel components, new `StateOrb` component

1. Add AnimatePresence to EventStream for entry animations
2. Create StateOrb component with pulsing glow
3. Add counter value pop animation (scale on change)
4. Add progress bar smooth transitions
5. State change cascade (staggered border transitions)
6. Command submit flash effect

**Estimated effort:** 3-4 hours
**Impact:** Makes the interface feel alive and responsive

### Phase 3: Neural Feed Formatting

**Files to change:** `EventStream.tsx` (rename to `NeuralFeed.tsx`)

1. Implement EVENT_CONFIG with semantic formatting per event type
2. Commentary frosted glass cards
3. Injection red pulse borders
4. Recency opacity fade
5. Proper human-readable event text (no more JSON.stringify)

**Estimated effort:** 2-3 hours
**Impact:** Transforms raw data dump into AI thought stream

### Phase 4: Layout + Widget Consolidation

**Files to change:** `App.tsx`, merge StatusPanel+CountersPanel

1. Merge StatusPanel + CountersPanel + DefensePanel into VitalsPanel sidebar
2. Create DefenseStrip (slim horizontal)
3. Redesign CommandBar as NeuralPrompt with contextual buttons
4. Adjust layout proportions (65/35 split)

**Estimated effort:** 3-4 hours
**Impact:** Better information hierarchy and breathing room

### Phase 5: Polish + Delight

1. Sound integration (Web Audio API hooks)
2. Easter eggs
3. Sparkline SVG component
4. Score panel with animated reveal
5. Keyboard shortcut hints

**Estimated effort:** 2-3 hours
**Impact:** Surprise and delight at the event

---

## 14. Venue Projection Considerations

This dashboard will be projected onto a venue screen for audience viewing at NEBULA:FOG 2026.

1. **Readability at distance:** Use text-xl+ for key data (elapsed, score, state). Generous spacing.
2. **High contrast:** Dark background (#06060c) with bright accents -- good for projectors.
3. **Large state indicator:** State orb + label should be readable from 30+ feet.
4. **Animation visibility:** Frosted glass blur effects will look stunning on projection. Ensure glow effects have enough intensity (not too subtle).
5. **No rapid flashing:** No sub-200ms flashes for audience epilepsy safety. Minimum pulse speed: 800ms.
6. **Color blindness:** Don't rely solely on red/green distinction -- use icons and text labels alongside color.
7. **Aspect ratio:** Design for 16:9 projection. Current flex layout should work but test at large viewport.
8. **Font size:** Minimum 14px for projected text, 18px+ preferred for key data.

---

## 15. File Mapping (Current -> Proposed)

| Current File | Proposed Rename | Key Changes |
|---|---|---|
| `App.tsx` | `App.tsx` | New layout, state theme provider |
| `components/Header.tsx` | `components/NeuralHeader.tsx` | Gradient shimmer, state orb, tracking |
| `components/StateIndicator.tsx` | `components/StateOrb.tsx` | Animated pulsing glow orb |
| `components/ConnectionDot.tsx` | `components/ConnectionDot.tsx` | Smaller, less prominent |
| `components/CommandBar.tsx` | `components/NeuralPrompt.tsx` | Contextual buttons, input styling |
| `panels/EventStream.tsx` | `panels/NeuralFeed.tsx` | Semantic formatting, AnimatePresence, commentary cards |
| `panels/StatusPanel.tsx` | *(merged into VitalsPanel)* | -- |
| `panels/CountersPanel.tsx` | *(merged into VitalsPanel)* | -- |
| `panels/DefensePanel.tsx` | `panels/DefenseStrip.tsx` + *(shield in VitalsPanel)* | Split defense data |
| `panels/ScorePanel.tsx` | `panels/ScoreReveal.tsx` | Animated score reveal |
| *(new)* | `panels/VitalsPanel.tsx` | Merged sidebar: state, team, counters, shield, sparkline |
| *(new)* | `hooks/useStateTheme.ts` | Dynamic CSS custom properties per state |
| *(new)* | `hooks/useAudioFeedback.ts` | Web Audio API tones |
| `styles/index.css` | `styles/index.css` | Complete palette overhaul, glass utilities, animations |
| `store/operatorStore.ts` | `store/operatorStore.ts` | Add event history for sparkline, roast tracking |

---

*This blueprint synthesizes research from sci-fi film UI/UX patterns (Ex Machina, Her, Blade Runner 2049, Westworld) with web frontend capabilities (Framer Motion, CSS backdrop-filter, Tailwind CSS 4, Web Audio API) to create a transformation plan that is cinematically compelling, technically specific, and implementable within the existing React + TypeScript + Vite stack.*
