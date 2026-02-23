# Arbiter Animation Design Concept
## NEBULA:FOG 2026 - AI Judge Visual Identity

---

## 1. Visual Identity: The Sigil

**Recommendation: Option B Hybrid — GSAP SVG "Sigil" + CSS Particle Field**

Arbiter is not a friendly assistant. It is an adjudicator. Its visual identity should evoke a **tribunal seal** — geometric, authoritative, slightly unsettling. Think less "Siri orb" and more "arcane security glyph that happens to be sentient."

### The Core Form: "The Sigil"

A centered SVG composition of three concentric geometric rings:

```
            ╭─────────────────╮
           ╱   ╭───────────╮   ╲
          │   ╱  ╭───────╮  ╲   │
          │  │  ╱ ARBITER ╲  │  │
          │  │  ╲  CORE   ╱  │  │   ← Inner ring: emotion reactor
          │   ╲  ╰───────╯  ╱   │   ← Middle ring: state indicator
           ╲   ╰───────────╯   ╱    ← Outer ring: data scanner
            ╰─────────────────╯
```

- **Outer Ring** (r=180px): 12-segment dashed stroke that rotates slowly. Segments light up as data flows in. During `thinking`, all segments pulse in sequence like a radar sweep. During `injection_blocked`, segments flash red and reverse direction.

- **Middle Ring** (r=120px): Solid stroke with variable dash-offset animation. Its color reflects the current macro-state (idle=dim cyan, thinking=bright cyan, speaking=emotion color, scoring=gold). Morphs between circle/hexagon/octagon based on state.

- **Inner Core** (r=60px): A filled shape that breathes. This is the emotion reactor — its color, scale, and blur respond directly to `commentarySentences[i].emotion`. It pulses on each new sentence arrival like a heartbeat.

### Why Not an Orb?

Every AI product ships an orb. Arbiter is a judge at a security hackathon. The geometric sigil reads as:
- **Authoritative** — institutional, seal-like
- **Technical** — geometric precision, not organic softness
- **Readable at 8m** — high-contrast concentric rings read as a clear silhouette
- **Distinct** — no one at the event will mistake it for ChatGPT

### Ambient Background: CSS Particle Grid

Behind the sigil, a grid of small dots (4px, 20% opacity) arranged in a 40px grid pattern. These dots drift subtly and brighten near the sigil. Implemented with CSS animations on a canvas element — no Three.js dependency needed for v1. This keeps bundle size minimal and performance safe on any projector laptop.

---

## 2. State Machine Design

Each state has three visual layers:
- **Ambient** = background particle grid behavior
- **Sigil** = the central geometric form
- **Event** = one-shot flashes, shakes, bursts on transitions

### IDLE (between demos)

- **Ambient**: Grid dots drift slowly in a circular pattern. Very dim (15% opacity). Slight wave motion.
- **Sigil**: Outer ring rotates at 0.5rpm. Middle ring is dim cyan, barely visible. Inner core breathes slowly (scale 0.95-1.05 over 4s). Overall opacity 60%.
- **Event**: None. This is the resting state.
- **Text**: "Awaiting next demo..." below sigil, dim, pulsing.
- **Transition IN**: Sigil fades down from previous state over 1.5s. Rings decelerate.

### THINKING (capture_started → first commentary)

- **Ambient**: Grid dots brighten to 40% and begin flowing inward toward sigil center, like data being absorbed. Speed increases over time.
- **Sigil**: Outer ring accelerates to 3rpm. Segments light up sequentially (radar sweep). Middle ring morphs from circle to hexagon. Inner core pulses faster (1.5s cycle), bright cyan. Scan line sweeps across the sigil vertically.
- **Event**: On entry, a radial shockwave ripple expands outward from sigil center (single ring, 0.4s).
- **Text**: Team name above sigil. "ARBITER IS ANALYZING..." below with dots.
- **Transition IN**: Shockwave burst → rings spin up over 0.8s.

### SPEAKING (commentary delivery)

This is the primary state. The sigil becomes an emotion reactor.

- **Ambient**: Grid dots adopt the current emotion's secondary color at 25% opacity. Dots near the sigil pulse on each new sentence arrival.
- **Sigil**: Outer ring rotation matches "session intensity" (rolling average of recent emotions — calm emotions slow it, intense ones speed it). Middle ring takes the emotion's primary color with a 0.6s crossfade. Inner core scales up on sentence arrival (1.0 → 1.15 over 0.2s, then back over 0.4s) — a visible "speaking" pulse.
- **Event**: Each new sentence triggers a subtle ring-shaped pulse outward from the inner core (0.3s, emotion-colored, 30% opacity). High-intensity emotions (amazed, excited, disappointed) get a double-pulse.
- **Text**: Commentary sentences below sigil, emotion-colored per sentence (existing behavior preserved).
- **Transition IN**: From thinking, rings smoothly shift color. Inner core "ignites" with first emotion color.

### QUESTIONING (Q&A mode)

- **Ambient**: Grid dots freeze in place and dim slightly. Stillness = anticipation.
- **Sigil**: All three rings pulse simultaneously in amber/orange (#ff8c00). Inner core morphs to a diamond shape (rotated square). The effect should feel interrogative — like a raised eyebrow.
- **Event**: On entry, rings contract inward 10% then expand back (a "lean forward" gesture, 0.5s).
- **Text**: Large italic question text below sigil.
- **Transition IN**: Rings snap to orange, contract-expand gesture.

### SCORING (criterion reveal + total)

- **Ambient**: Grid dots arrange into faint vertical columns (suggesting a bar chart / data structure). Gold tint.
- **Sigil**: Positioned top-center of screen (smaller, 60% size) to make room for score bars below. Outer ring segments fill in one-by-one as criteria arrive (12 segments, map criteria count to segments). Middle ring color reflects running score average via scoreColor(). Inner core grows slightly with each criterion.
- **Event**: Each criterion arrival triggers a segment flash on the outer ring. On score_total, the entire sigil does a scale-up burst (1.0→1.3→1.0 over 0.6s) with the final score color.
- **Text**: Score bars and criterion rows below the sigil (existing layout preserved).
- **Transition IN**: Sigil floats upward and shrinks to top position (0.6s ease-out).

### DELIBERATING (final rankings)

- **Ambient**: Grid dots form a slow vortex pattern rotating around the sigil. Deep purple tint. Gravitas.
- **Sigil**: Maximum intensity. All rings at full brightness. Outer ring has doubled stroke width. Rotation slows to 1rpm (deliberate, weighty). Colors cycle through gold → cyan → white.
- **Event**: Each ranking arrival triggers a horizontal line that sweeps across the screen (like a scan line). Winner reveal (#1 rank) triggers: sigil explodes to 150% scale, all rings flash gold, particle burst outward from center, then settle back.
- **Text**: Rankings table below. Narrative block at bottom.
- **Transition IN**: Slow dramatic fade-in over 1.2s. Rings spin up from zero.

### ALERT (injection_blocked)

This is an overlay state that interrupts everything.

- **Ambient**: All grid dots flash red and scatter outward (explosion pattern). Then reform.
- **Sigil**: Rings shatter — the three rings separate outward with rotation, then snap back together after 0.5s. Color: all red. Inner core flashes rapidly.
- **Event**: Screen border flashes red. A "glitch" effect — horizontal displacement of the sigil for 2-3 frames (CSS transform jitter). CRT scanline overlay for 0.5s.
- **Text**: Existing injection alert overlay (red backdrop, roast text). Sigil visible behind at 30% opacity.
- **Transition IN**: Instant (0ms). Violence of the transition IS the message.
- **Transition OUT**: Sigil rings reassemble over 0.8s. Grid dots flow back to positions. Color returns to previous state.

---

## 3. Emotion Palette

Each emotion maps to visual parameters that drive the sigil's inner core and middle ring.

### Warm/Positive Cluster

| Emotion | Primary | Secondary | Intensity | Ambient Behavior | Transition Feel |
|---|---|---|---|---|---|
| **excited** | #00ff88 | #00cc66 | 0.9 | Dots pulse rapidly, expand outward | Electric snap — fast color shift, ring speed doubles momentarily |
| **amazed** | #00d4ff | #7b61ff | 0.95 | Dots spiral outward in burst | Explosive — scale burst on inner core, bright flash |
| **impressed** | #00d4ff | #00ff88 | 0.7 | Dots drift upward gently | Smooth swell — rings brighten over 0.4s |
| **proud** | #ffd700 | #ff8c00 | 0.75 | Dots form loose crown pattern above sigil | Regal — slow golden glow builds from center |
| **encouraging** | #00ff88 | #00d4ff | 0.5 | Dots pulse gently in sync | Warm push — soft outward pulse |
| **supportive** | #00d4ff | #a8b2d0 | 0.4 | Dots hold steady, faint glow | Gentle — minimal motion change, steady brightness increase |
| **content** | #a8b2d0 | #00d4ff | 0.3 | Dots slow to near-stillness | Settling — ring rotation decelerates, everything calms |

### Cool/Analytical Cluster

| Emotion | Primary | Secondary | Intensity | Ambient Behavior | Transition Feel |
|---|---|---|---|---|---|
| **confident** | #00d4ff | #f0f0f0 | 0.6 | Dots align into clean grid | Crisp — sharp color transition, no easing |
| **thoughtful** | #7b61ff | #a8b2d0 | 0.45 | Dots orbit sigil slowly in elliptical paths | Contemplative — slow fade, ring rotation slows |
| **curious** | #ff8c00 | #ffd700 | 0.55 | Dots cluster and disperse rhythmically | Probing — middle ring morphs slightly toward a triangle, then back |
| **constructive** | #00ff88 | #ffd700 | 0.5 | Dots flow in structured lines | Methodical — clean, even transitions |

### Edge/Negative Cluster

| Emotion | Primary | Secondary | Intensity | Ambient Behavior | Transition Feel |
|---|---|---|---|---|---|
| **sarcastic** | #ffd700 | #ff8c00 | 0.65 | Dots jitter with micro-randomness | Wry — asymmetric pulse (fast in, slow out) |
| **ironic** | #ff8c00 | #ffd700 | 0.6 | Dots briefly reverse direction | Twist — rings counter-rotate for 0.3s then resume |
| **skeptical** | #ff8c00 | #ff4444 | 0.55 | Dots contract inward slightly | Narrowing — rings tighten, inner core shrinks 5% |
| **disappointed** | #ff4444 | #ff8c00 | 0.7 | Dots sink downward, dim | Heavy — everything decelerates, color drains to red slowly over 0.8s |
| **surprised** | #7b61ff | #00d4ff | 0.85 | Dots scatter then regroup | Jolt — instant scale spike (1.0→1.2→1.0 in 0.3s), ring speed spikes |

### Intensity Scale Reference

- 0.0-0.3: Minimal sigil response. Ambient barely changes. Calm water.
- 0.3-0.6: Visible color shifts and moderate ring speed changes. Engaged.
- 0.6-0.8: Clear animation events. Audience notices the shift. Active.
- 0.8-1.0: Maximum expression. Particle bursts, scale changes, bright flashes. Peak moments.

---

## 4. Screen-by-Screen Integration

### Layout Architecture

The sigil lives in a persistent layer that spans the full viewport, behind all text content but above the particle grid background. Three z-layers:

```
z-0:  Particle Grid Background (full viewport, CSS/canvas)
z-10: Sigil Layer (centered, SVG + Framer Motion)
z-20: Content Layer (text, scores, tables — existing screens)
z-30: Overlay Layer (injection alert)
```

### IdleScreen

```
┌─────────────────────────────────────────────┐
│  ARBITER                              [dot] │  ← header
├─────────────────────────────────────────────┤
│                                             │
│             ·  ·  ·  ·  ·  ·               │  ← particle grid
│          ·    ╭─ ─ ─ ─ ─╮    ·             │
│        ·     ╱  ╭─────╮  ╲     ·           │
│       ·     │  │ CORE  │  │     ·          │  ← sigil at 60% opacity
│        ·     ╲  ╰─────╯  ╱     ·           │
│          ·    ╰─ ─ ─ ─ ─╯    ·             │
│             ·  ·  ·  ·  ·  ·               │
│                                             │
│           Awaiting next demo...             │  ← pulsing text
│                                             │
├─────────────────────────────────────────────┤
│         NEBULA:FOG 2026 - AI Judging        │
└─────────────────────────────────────────────┘
```

- Sigil: centered, full size, dim. Breathing slowly.
- Text: single line below sigil center.
- Data driver: none (static state).

### ThinkingScreen

```
┌─────────────────────────────────────────────┐
│  ARBITER                              [dot] │
├─────────────────────────────────────────────┤
│              TEAM PHOENIX                   │  ← team name, cyan
│              offensive track                │  ← track, muted
│                                             │
│          ·→   ╭─ ─ ─ ─ ─╮   ←·            │  ← dots flow inward
│        ·→    ╱  ╭─────╮  ╲    ←·           │
│       ·→    │  │ ████  │  │    ←·          │  ← bright pulsing core
│        ·→    ╲  ╰─────╯  ╱    ←·           │
│          ·→   ╰─ ─ ─ ─ ─╯   ←·            │
│                 ━━━━▶━━━━                   │  ← scan line overlay
│                                             │
│         ARBITER IS ANALYZING...             │  ← pulsing text
│              · · · · ·                      │  ← animated dots
│           ━━━━━━━━▶━━━━━━━━                │  ← scan bar
│        Processing demo output               │
├─────────────────────────────────────────────┤
│         NEBULA:FOG 2026 - AI Judging        │
└─────────────────────────────────────────────┘
```

- Sigil: centered, full size, bright. Rings accelerated. Radar sweep on outer ring.
- Text: team info above sigil, analyzing text below.
- Data driver: `thinkingTeam.teamName`, `thinkingTeam.track`.

### CommentaryScreen

```
┌─────────────────────────────────────────────┐
│  ARBITER                              [dot] │
├─────────────────────────────────────────────┤
│              TEAM PHOENIX                   │
│                                             │
│     ·    ╭─ ─ ─╮                            │
│    ·    │ CORE │     "Their SQL injection   │  ← sigil moves to left
│     ·    ╰─ ─ ─╯     approach was textbook  │     third of screen
│                       but the WAF bypass     │
│                       genuinely surprised    │  ← sentences stack,
│                       me. Bold move."        │     emotion-colored
│                                             │
├─────────────────────────────────────────────┤
│         NEBULA:FOG 2026 - AI Judging        │
└─────────────────────────────────────────────┘
```

- Sigil: moves to left-center (30% from left edge), scales to 70%. This gives commentary text the right 60% of the screen. The sigil becomes a "speaker portrait" — you watch it react while reading the words.
- Text: team name top-center, sentences right-aligned with emotion colors.
- Data driver: `commentarySentences[i].emotion` drives sigil color per sentence. Each arrival triggers a speaking pulse on the inner core.
- Special behavior: The latest sentence's emotion controls the sigil. Previous sentence colors persist in the text but not in the sigil animation.

### QuestionScreen

```
┌─────────────────────────────────────────────┐
│  ARBITER                              [dot] │
├─────────────────────────────────────────────┤
│              TEAM PHOENIX                   │
│                                             │
│               ╭─ ─ ─ ─ ─╮                  │
│              ╱  ╭─◇──╮  ╲                  │  ← diamond inner core
│             │  │  ◇◇  │  │                 │     amber/orange color
│              ╲  ╰──◇─╯  ╱                  │
│               ╰─ ─ ─ ─ ─╯                  │
│                                             │
│     Q: How would your approach handle       │
│     a polymorphic payload that mutates      │  ← large italic text
│     between inspection passes?              │
│                                             │
├─────────────────────────────────────────────┤
│         NEBULA:FOG 2026 - AI Judging        │
└─────────────────────────────────────────────┘
```

- Sigil: centered, 80% size. All rings pulse amber. Inner core in diamond morph. The "lean forward" contraction plays on entry.
- Text: question below sigil, large and italic.
- Data driver: static orange state (no per-sentence emotion here).

### ScoreCardScreen

```
┌─────────────────────────────────────────────┐
│  ARBITER      ╭─ ─ ─╮               [dot]  │
│            ──│ CORE │──                     │  ← small sigil in header
│               ╰─ ─ ─╯                      │
│          Score Reveal — TEAM PHOENIX        │
├─────────────────────────────────────────────┤
│                                             │
│  Exploitation Depth    (x2.0)         8.5   │
│  ████████████████████████████████░░░░       │
│  Impressive persistence through layers      │
│                                             │
│  Defense Evasion       (x1.5)         7.2   │
│  ██████████████████████████░░░░░░░░░       │
│  Standard but effective approach            │
│                                             │
│  ... more criteria ...                      │
│                                             │
│              Total Score                    │
│                 8.1                          │  ← large, color-coded
│             Track: Offensive                │
├─────────────────────────────────────────────┤
│         NEBULA:FOG 2026 - AI Judging        │
└─────────────────────────────────────────────┘
```

- Sigil: shrinks to 40% size and floats into upper area between header and score title. Acts as a "seal of judgment." Outer ring segments fill as criteria arrive.
- Text: existing score layout below, unchanged.
- Data driver: `criteria.length` fills outer ring segments. `scoreTotal.totalScore` drives final color burst via `scoreColor()`.

### DeliberationScreen

```
┌─────────────────────────────────────────────┐
│  ARBITER                              [dot] │
├─────────────────────────────────────────────┤
│            Final Deliberation               │
│                                             │
│          ╭─ ─ ─ ─ ─ ─ ─ ─╮                │
│         ╱  ╭─══════─╮  ╲                   │  ← max intensity sigil
│        │  ║  CORE   ║  │                    │     doubled stroke
│         ╲  ╰─══════─╯  ╱                   │
│          ╰─ ─ ─ ─ ─ ─ ─ ─╯                │
│                                             │
│  #5  Team Delta      6.2  defensive  ...    │
│  #4  Team Gamma      6.8  offensive  ...    │  ← rankings arrive
│  #3  Team Beta       7.4  offensive  ...    │     worst-first
│  #2  Team Alpha      8.1  defensive  ...    │
│  #1  TEAM PHOENIX    8.9  offensive  WIN    │  ← gold flash
│                                             │
│  [Narrative block]                          │
├─────────────────────────────────────────────┤
│         NEBULA:FOG 2026 - AI Judging        │
└─────────────────────────────────────────────┘
```

- Sigil: centered above rankings table, 70% size. Maximum visual intensity. Rings doubled stroke width, slow authoritative rotation.
- Text: rankings table below, narrative at bottom.
- Data driver: `rankings.length` drives gravitas buildup. Winner reveal (`rank === 1`) triggers the gold explosion burst.

### IntermissionScreen

```
┌─────────────────────────────────────────────┐
│  ARBITER                              [dot] │
├─────────────────────────────────────────────┤
│              Leaderboard                    │
│                                             │
│  [42 Injection Attempts Blocked]            │  ← red badge
│                                             │
│  #1  Team Phoenix    8.9  offensive         │
│  #2  Team Alpha      8.1  defensive         │
│  #3  Team Beta       7.4  offensive         │
│  ... leaderboard ...                        │
│                                             │
│        ╭─ ─ ─╮                              │
│       │ core │  Next Demo Incoming...       │  ← small sigil, idle
│        ╰─ ─ ─╯                              │
├─────────────────────────────────────────────┤
│         NEBULA:FOG 2026 - AI Judging        │
└─────────────────────────────────────────────┘
```

- Sigil: bottom-center, 35% size, idle breathing. The leaderboard is the star here, not the sigil.
- Text: existing leaderboard layout dominates.
- Data driver: minimal. Sigil returns to idle behavior.

---

## 5. Feasibility Recommendation

### Recommended Approach: Option A+ (Enhanced Quick Win)

**Not pure Option A (ElevenLabs orb). Not full Option B (GSAP SVG face). A targeted hybrid that ships fast and looks intentional.**

#### Rationale

- The event is approaching. Option C (full GLSL shader, 2-3 weeks) is eliminated.
- Option B's full GSAP SVG face with Three.js particle background (5-7 days) is achievable but risky if the team has other event prep work.
- The sigil concept described above can be implemented as **pure SVG + Framer Motion + CSS**, using dependencies already in the project. Zero new packages needed.

#### What "Option A+" Means

Use the existing stack (React + Framer Motion + Tailwind + Zustand) to build the sigil animation system. No Three.js. No GSAP. No new dependencies. The sigil is SVG elements animated with Framer Motion's `animate` and `transition` props — the same API already used throughout every screen component.

The particle grid background is a CSS grid of `div` elements with Framer Motion animations, or a lightweight `<canvas>` 2D context if performance requires it.

#### Phased Rollout

**Phase 1 — Ship in 2 days: "The Sigil Breathes"**

Highest-impact, lowest-risk changes:

1. Add `<ArbiterSigil />` component — three concentric SVG circles with Framer Motion rotation, color, and scale animations.
2. Add it to `ScreenRouter` as a persistent background layer (z-10) that every screen renders behind.
3. Wire `activeScreen` to sigil state (idle/thinking/speaking/questioning/scoring/deliberating).
4. Wire `commentarySentences[latest].emotion` to sigil color during commentary.
5. Restructure `CommentaryScreen` to position text to the right, sigil to the left.

No particle grid yet. No per-emotion ambient behaviors. Just the core sigil responding to state and emotion. This alone transforms the display from "text dashboard" to "living entity."

**Phase 2 — Ship in 2 more days: "The Sigil Speaks"**

1. Add speaking pulse (inner core scale bump on each new sentence).
2. Add emotion transition animations (crossfade colors, intensity-based ring speed).
3. Add entry/exit event flashes (shockwave on thinking entry, gold burst on score total).
4. Add the "shatter and reassemble" effect for injection alerts.
5. Add the diamond morph for question state.

**Phase 3 — If time permits: "The World Reacts"**

1. Add CSS particle grid background.
2. Wire particle behaviors to emotion state (drift patterns, color tints).
3. Add sigil position/scale transitions per screen (left-align for commentary, top for scoring, etc.).
4. Polish transition timings between all state pairs.

#### The Single Highest-Impact Change

**Add the sigil to the thinking screen and wire its color to commentary emotions.**

Right now, the thinking screen is text that says "ARBITER IS ANALYZING..." — informative but inert. Adding a geometric form with animated rings that visibly accelerate, then shift color as emotions arrive during commentary, is the single change that makes Arbiter feel alive. It can be built and integrated in under a day using existing Framer Motion patterns already proven throughout the codebase.

---

## Implementation Notes

### New Files Needed

```
src/components/ArbiterSigil.tsx    — SVG sigil component with Framer Motion
src/lib/emotionConfig.ts           — Emotion-to-visual-parameter mapping table
src/components/ParticleGrid.tsx    — Background particle layer (Phase 3)
```

### Store Changes

Add to `displayStore.ts`:

```typescript
// New derived state for animation system
currentEmotion: string;           // Latest emotion from commentarySentences
previousEmotion: string;          // For crossfade transitions
emotionIntensity: number;         // From emotionConfig lookup
sessionIntensity: number;         // Rolling average (last 5 emotions)
```

### Performance Budget

- Sigil SVG: 3 animated elements (rings) + 1 animated fill (core) = 4 Framer Motion instances. Well within budget.
- Particle grid (Phase 3): Target 200 dots max. CSS transforms only (GPU-composited). No layout thrashing.
- Total animation frame budget: <4ms per frame on a mid-range laptop driving a projector at 60fps.

### Key Design Constraints

1. **No WebGL/Three.js in v1.** The projector laptop is an unknown quantity. 2D animations with CSS/SVG are universally safe.
2. **Monospace typography preserved.** The sigil adds visual life without changing the information design.
3. **Existing screen layouts are non-destructive.** The sigil is a new layer behind existing content. If it breaks, remove the component and everything still works.
4. **Color palette respected.** All emotion colors derive from the existing palette (#00d4ff, #ffd700, #ff4444, #00ff88, #ff8c00) plus two additions: purple (#7b61ff) for thoughtful/surprised, and the existing muted (#a8b2d0) for content/supportive.

---

*Document authored for NEBULA:FOG 2026 Arbiter animation system. Ready for implementation review.*
