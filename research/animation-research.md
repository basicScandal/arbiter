# Arbiter AI Judge — Animation Research Report
**NEBULA:FOG 2026 Security Hackathon**
*Researched: 2026-02-23*

---

## Executive Summary

The Arbiter is an AI judge that watches live security demos, generates emotion-tagged commentary, scores teams, and asks questions — all projected on a large screen for a live audience. This document synthesizes research across five areas: live event AI visualizations, emotion-reactive animation techniques, interactive audience experiences, browser animation technologies, and notable inspiration examples.

The core design challenge: make the audience feel they are watching an *intelligent entity* that genuinely reacts — not a dashboard. The animation should signal emotional state through ambient visual language, not explicit labels.

---

## 1. Live Event AI Visualizations

### Conference Stage Displays

**GitHub Universe 2024** (Fort Mason, San Francisco) used broadcast-ready motion graphics with animated lower-thirds, openers, multi-venue synchronized screen playback, and dynamic branded visuals across 5 live stages. Their production approach: every state transition (speaker intro, demo, Q&A) had a corresponding motion asset.

The GitHub Copilot character itself uses a sophisticated state machine with 4 stages per animation: Idle → Starting → Running → Ending. A Director component evaluates conditions (error state, "thinking" state, sentiment polarity of response) and triggers the Actor state machine accordingly. Animations were built in Blender/After Effects, converted to SVG sprite sheets, and driven entirely with CSS — enabling color-mode support and zero JS overhead for playback.

**Google I/O 2025** opened with a video generated entirely by Veo/Imagen AI models before Sundar Pichai walked onstage — the AI's *output* was itself the visual spectacle. Google Beam demonstrated real-time 2D→3D video rendering for presence-at-scale.

**Key takeaway:** Top-tier tech conferences use motion as a narrative layer, not decoration. Every distinct phase of an event has a visual "mode."

### Esports Overlay Systems

The 2024 League of Legends World Championship Finals used AWS Win Probability — an ML model running every second of gameplay, visualizing binary win prediction as a live ambient bar. This is a direct parallel to Arbiter's scoring: a continuously updating signal rendered as a persistent ambient element.

WEAVR (University of York) builds cross-reality esports viewing with real-time data-driven overlays across VR, AR, and 2D screens. Their research shows audiences engage most with overlays that *anticipate* events (predictive) rather than just confirm them.

Resonance (AI DJ hype system) calculates a crowd energy score from live video/audio and displays it as a persistent hype graph — ambient, non-intrusive, always present.

**Key takeaway:** The most effective live event displays run a persistent "ambient signal" (score, energy, probability) alongside episodic "event flashes" (kill feed, team scores). Arbiter needs both layers.

---

## 2. Emotion-Reactive Animation Techniques

### Color Palette Mapping

Color psychology research in animation establishes these mappings with high confidence:

| Arbiter Emotion | Palette | Visual Character |
|---|---|---|
| **impressed** | Electric blue → gold | Bright, expansive, high energy |
| **sarcastic** | Desaturated green → cold grey | Flat affect, minimal motion |
| **disappointed** | Muted orange → dark burgundy | Contracting, slow pulse |
| **encouraging** | Warm amber → soft green | Gentle, outward expansion |
| **skeptical** | Cool blue-grey → steel | Slow oscillation, narrow bandwidth |
| **proud** | Deep purple → bright violet | Slow bloom, high saturation |
| **excited** | Hot pink → electric yellow | High frequency, wide amplitude |
| **neutral** | Soft white → mid-grey | Steady slow pulse |

Warm tones (red, orange, yellow) signal energy, passion, optimism. Cool tones (blue, grey) signal analysis, detachment, skepticism. Saturation level maps to emotional intensity. Animation speed maps to arousal level.

### Particle System Behavior per Emotion

- **Impressed:** Particles accelerate outward from center, trails lengthen, colors brighten
- **Sarcastic:** Particles slow, drift aimlessly, slight clockwise drift, desaturated
- **Disappointed:** Particles fall downward under simulated gravity, fade to dark
- **Skeptical:** Particles orbit slowly in tight radius, no expansion
- **Proud:** Slow radial bloom, particles spread wide and hold position
- **Encouraging:** Gentle upward drift, soft green trails, warm light pulse
- **Excited:** High-velocity burst, short-lived particles, rapid color cycling

### Waveform/Audio-Style Patterns

The Apple Siri waveform (iOS 18) uses a multi-band sine wave that responds to both input and output volume, with color shifting based on mode (listening = green/blue, speaking = white/warm). The `kopiro/siriwave` JS library replicates this cleanly. The ElevenLabs Orb extends this to a full 3D WebGL sphere.

For Arbiter: commentary is text, not audio — but the *speaking speed* (words-per-minute of the displayed text) and *sentence sentiment intensity* can drive the same parameters that audio volume normally controls.

### Character Expression Systems

**Live2D / VTuber approach:** Draws expressions in parameter layers (mouth open, eyebrow raise, eye squint) and interpolates between them via numeric inputs. The Open-LLM-VTuber project maps LLM emotion outputs to Live2D expression parameters in real-time. "Virtual You" and "Nyx" use voice pitch analysis to drive avatar emotion states.

**For Arbiter:** Since the AI tags each sentence with an emotion label, those labels become the numeric inputs to the expression system. No audio analysis needed — the AI itself drives the state.

---

## 3. Interactive Audience Experiences

### What Makes a Projected Display Feel Alive

Research from esports and live event production identifies three layers:

1. **Ambient Layer** (always on): A persistent visual signal that slowly evolves — a pulsing orb, a score ring, an energy field. Gives the audience something to read at a glance without requiring attention.

2. **Event Layer** (triggered): Momentary flashes when something significant happens — new score submitted, question asked, emotion spike. Short, punchy, high-contrast.

3. **Content Layer** (text/data): The actual commentary, score, team name. Should never compete with the ambient layer — legibility is primary.

For large projected screens, contrast ratios matter far more than detail. Effects visible at 3m on a laptop look very different at 8m on a projector. Design for silhouette readability.

### Energy/Intensity Visualization

The Resonance DJ hype system pattern: maintain a rolling average of intensity, display it as a persistent ambient glow, and spike it on peaks. Applied to Arbiter: maintain a "session intensity" score (average of emotional intensity across all scored teams) as the background ambient state, with per-sentence emotion driving the event layer.

### Transition Animations Between States

State machines with 4-stage transitions (GitHub Copilot model) perform better than direct cuts:
- **Idle → Active:** Slow bloom/expansion (300-500ms)
- **Active → Emotion Flash:** Immediate color shift + particle burst (100ms)
- **Emotion Flash → Settle:** Gradual return to ambient (500-800ms)
- **Active → Idle:** Slow contraction/dim (800ms)

Audiences read intention from transition *shape*, not just transition *duration*.

---

## 4. Technical Approaches — Ranked by Impact vs. Performance

### Tier 1: Best for Arbiter

#### Three.js + React Three Fiber + GLSL Shaders
**Visual impact: 10/10 | Performance: 8/10 | Dev complexity: 7/10**

- WebGL runs on GPU, not CPU — particle systems of 50k+ elements at 60fps are routine
- GLSL fragment shaders can compute per-pixel plasma/fluid effects with zero JS overhead
- React Three Fiber (`@react-three/fiber`) provides idiomatic React API over Three.js
- `InstancedMesh` for particle systems avoids per-object draw call overhead
- WebGPU (available Chrome/Edge stable, Safari/Firefox behind flag) offers 150x particle improvement
- ElevenLabs Orb is open source, built on this exact stack — it's a working reference implementation

**For Arbiter:** The orb/sphere approach with GLSL-driven color and turbulence uniforms driven by emotion state is the highest-impact option. Emotion changes update shader uniforms; the GPU handles the rest.

#### Rive + State Machine
**Visual impact: 8/10 | Performance: 9/10 | Dev complexity: 5/10**

- Rive's state machine has direct support for multi-layer simultaneous animation (body motion + facial expression + accessory = separate layers, all running at once)
- Data binding (2024 feature) connects runtime data directly to animation parameters — perfect for WebSocket-driven emotion updates
- @rive-app/react-canvas wraps WASM engine for React; the useRive hook manages lifecycle
- Vector-based, scales perfectly to any projector resolution
- Exported .riv files are compact; no runtime JS animation calculations
- Rive vs. Lottie: Lottie plays back pre-authored animations; Rive runs *logic* — it can make decisions based on state inputs

**For Arbiter:** Design a character/entity in Rive with emotion state as numeric inputs. The WASM runtime evaluates transitions and blends. Excellent option if a designer is involved.

### Tier 2: Strong Supporting Role

#### GSAP + SVG Morphing (MorphSVGPlugin)
**Visual impact: 7/10 | Performance: 9/10 | Dev complexity: 5/10**

- GSAP directly manipulates DOM/canvas/SVG objects, bypassing React's render cycle
- MorphSVGPlugin morphs any SVG path to any other path — emotion expressions as SVG shapes
- Can control Three.js/canvas object properties in the same timeline
- ~23KB gzipped core; significantly faster than Framer Motion for complex sequences
- Sprite sheet approach (GitHub Copilot model): pre-author emotion expressions as SVGs, morph between them on state change
- Runs on compositor thread — layout-thrashing-free 60fps

**For Arbiter:** Works best as the *event layer* driver — GSAP timelines triggered by WebSocket emotion events, morphing face/form elements while Three.js handles the ambient layer.

#### CSS Animations + Keyframes (with custom properties)
**Visual impact: 5/10 | Performance: 10/10 | Dev complexity: 3/10**

- Runs entirely on compositor thread — cannot drop frames
- CSS custom properties (`--emotion-hue`, `--pulse-speed`) updated from JS drive dynamic feel
- Cyberpunk glitch effects (`clip-path: inset()` within `@keyframes`, chromatic aberration via pseudo-elements) achievable in pure CSS
- Excellent for: text reveal effects, border animations, background pulse, overlay transitions
- Not suitable for: particle systems, 3D effects, procedural animation

**For Arbiter:** Best for the content layer (text commentary reveal, score display, team name transitions) and supplementary ambient glows/borders.

### Tier 3: Use Sparingly

#### Framer Motion
**Visual impact: 6/10 | Performance: 6/10 | Dev complexity: 2/10**

- Excellent for UI transitions (score panels sliding in/out, cards animating)
- Poor for high-frequency updates — layout calculations tied to React's render cycle; heavy state updates cause dropped frames
- 32KB gzipped; larger than GSAP
- `AnimatePresence` for enter/exit transitions is genuinely excellent
- Not suitable for: the main visual centrepiece, particle systems, anything running at >10 updates/second

**For Arbiter:** Use only for UI chrome — panel transitions, score reveals, team name cards.

#### Lottie / bodymovin
**Visual impact: 7/10 | Performance: 8/10 | Dev complexity: 3/10**

- After Effects → JSON → browser playback; great for polished pre-authored animations
- Vector-based, resolution-independent (important for projected display)
- No runtime logic — plays a sequence, can't branch based on real-time state
- Use case: pre-authored emotion *transition* clips (a 1-second "shifting to skeptical" clip between states)
- GitHub Copilot's Lottie animations are publicly available on LottieFiles as reference

**For Arbiter:** Pre-author 10-12 emotion transition clips in After Effects, play them on emotion state change as the event layer, while Three.js runs continuously underneath.

---

## 5. Notable Inspiration Examples

### Direct References

**ElevenLabs Orb** (https://ui.elevenlabs.io/docs/components/orb)
The closest existing implementation to what Arbiter needs. Open source, MIT licensed. Three.js + React Three Fiber + GLSL. Supports `null`, `thinking`, `listening`, `talking` states with distinct visual behaviors. Color customizable via props. Audio-reactive via `manualInput`/`manualOutput` props (0-1 normalized) — these can be driven by text sentiment intensity instead of audio volume. This is a working, production-ready starting point.

**Apple Siri iOS 18 Animation** (kopiro/siriwave on GitHub)
Multi-band sine waveform with color mode shifting. The JS library is standalone and can be embedded in React. The iOS 18 Figma community file documents the exact design parameters. Good reference for the "listening/processing" ambient state.

**GitHub Copilot State Machine Architecture** (github.blog/engineering)
Director + Actor pattern: one component evaluates conditions and selects animation mode; another runs the 4-stage (idle/starting/running/ending) state machine. This architectural pattern maps directly onto Arbiter's emotion pipeline: the WebSocket message is the Director's input, the animation component is the Actor.

**Spotify Wrapped 2024 Animation System** (medium.com/designright)
"Fluid grid system, flexible color palettes, and smooth animation work" — specifically: palette-per-mood, transitions that feel like personality shifts rather than state changes. Reference for how a brand/character expresses different emotional modes through color alone.

**Open-LLM-VTuber** (github.com/Open-LLM-VTuber)
Full open-source pipeline: LLM → emotion tags → Live2D expression parameters → real-time avatar. This is the closest existing system to Arbiter's commentary→emotion→animation pipeline. Study the emotion mapping layer.

**Resonance AI DJ Hype System** (trendhunter.com)
Real-time crowd energy visualization for live events. Ambient hype graph + instantaneous spike display. Direct analog for Arbiter's session intensity ambient layer.

**react-ai-orb** (github.com/Steve0929/react-ai-orb) and **ta-react-voice-orb** (github.com/Moe03/ta-react-voice-orb)
Smaller community implementations of audio-reactive orbs in React. Less polished than ElevenLabs but simpler codebases to study and extend.

---

## 6. Top 3 Recommended Approaches

### Option A: "The Entity" — ElevenLabs Orb Extended (Recommended Quick Win)

**Concept:** Start with the ElevenLabs open-source Orb component as the centrepiece. It already handles Three.js/GLSL rendering, React integration, and state-based visual changes. Extend it with Arbiter's emotion states by mapping emotion tags to color palettes and turbulence uniforms.

**Architecture:**
```
WebSocket message → emotion tag → React state update
  → orb colors prop (2-color gradient)
  → orb manualInput/manualOutput (0-1 intensity)
  → CSS event flash (border glow, text reveal)
  → Framer Motion (score panel transitions)
```

**Emotion → Visual mapping:**
- Color pair drives the gradient (e.g., impressed = `["#00d4ff", "#ffd700"]`)
- Intensity value (0.0–1.0) derived from emotion weight drives orb turbulence
- On high-intensity emotions, trigger a CSS border flash and particle burst over the orb

**Pros:**
- Working Three.js/GLSL foundation — no 3D from scratch
- Open source, installable via shadcn CLI
- 4 states already implemented; extending to 10+ emotions is prop changes + shader tweaks
- 60fps guaranteed (GPU-driven)
- Ships in 2-3 days of focused work

**Cons:**
- Orb metaphor is now common (every AI product uses an orb)
- Limited personality — feels like a product, not a *judge*
- Would need custom work to feel appropriately intimidating/authoritative for a security hackathon

---

### Option B: "The Arbiter" — GSAP + SVG Face + Three.js Background

**Concept:** Build a custom abstract "face" entity using SVG morphing (GSAP MorphSVGPlugin) for a central character element, with a Three.js particle field as the background ambient layer. The face morphs between emotion expressions; the particle field's behavior (velocity, color, density) reflects the emotional register.

**Architecture:**
```
WebSocket message → emotion tag
  → GSAP timeline: morph SVG face to emotion expression (200ms)
  → Three.js uniform update: particle color, velocity, density
  → CSS text layer: commentary reveal with emotion-tinted color
  → Score ring: SVG arc animation driven by score delta
```

**Emotion expression library (pre-authored SVGs):**
Each emotion gets a distinct abstract SVG "face" — not literally a human face, but geometric forms that read as expressions (wide/narrow eye shapes, curve of a mouth-analog element). Morphing between them takes 200ms with elastic easing.

**Pros:**
- Highest narrative impact — it genuinely looks like a judge character, not a visualizer
- GSAP + SVG is extremely reliable, no 3D expertise required for the face layer
- Three.js background adds depth without being the primary focus
- Character identity differentiates Arbiter from generic "AI product" aesthetics
- Appropriate for a security hackathon: abstract, slightly unsettling, authoritative

**Cons:**
- SVG expression design requires a designer (or careful geometric design from a developer)
- GSAP MorphSVGPlugin requires a paid GSAP Club membership (or use Flubber.js as free alternative)
- More moving parts than Option A
- 5-7 days of focused work

---

### Option C: "The Oracle" — Full Custom GLSL Shader Character (Dream Option)

**Concept:** A single fullscreen canvas driven by a custom GLSL fragment shader. The shader renders a plasma/fluid simulation where color, turbulence parameters, and waveform patterns are controlled by uniforms updated from WebSocket events. No Three.js — raw WebGL for maximum performance and control. Emotion states drive shader uniforms directly: hue rotation, turbulence frequency, vortex intensity, chromatic aberration amount.

**Architecture:**
```
WebSocket message → emotion tag
  → Emotion config object { hue, saturation, turbulence, speed, aberration }
  → Smooth LERP to new uniform values over 400ms (prevents jarring jumps)
  → Fullscreen canvas: plasma/fluid GLSL shader runs at GPU clock speed
  → Overlay layer: text, score, team info in CSS/HTML above the canvas
  → GSAP for overlay transitions
```

**Shader design:**
- Base: plasma/Perlin noise fluid simulation with time-varying parameters
- Impressed: fast outward expansion, gold/blue hue, high saturation burst
- Sarcastic: slow flat oscillation, desaturated green, minimal motion
- Skeptical: slow rotational waveform, cold steel blue, tight radius
- Disappointed: downward flow, dark reds, contracting spiral
- Proud: slow radial bloom, deep purples expanding to violet

**Pros:**
- Visually unlike anything else — genuinely stunning on a large screen
- Single canvas, GPU-driven: lowest possible CPU overhead
- Infinitely customizable: every emotion can have a completely distinct visual world
- No external animation library dependencies
- The "physics" of the shader feel organic and alive in ways pre-authored animations cannot

**Cons:**
- Requires GLSL shader expertise (or significant learning investment)
- Debugging shaders is harder than debugging JS
- 2-3 weeks of focused work for a polished result
- Risk: shader performance on specific GPU/driver combinations can be unpredictable

---

## 7. Quick Win vs. Dream

### Quick Win: Option A (ElevenLabs Orb Extended)

**Timeline:** 2-3 days
**What you get:** A polished, production-quality animated orb that reacts to emotion states in real-time via WebSocket. Colors shift per emotion. Turbulence intensity reflects emotional weight. Commentary text renders below with CSS-animated reveal. Score panel transitions with Framer Motion.

**Minimum implementation path:**
1. `npx shadcn@latest add "https://ui.elevenlabs.io/r/orb"` — install orb component
2. Map Arbiter emotion tags to color pairs and intensity values (config object, ~50 lines)
3. Hook WebSocket message handler to update orb props
4. Add CSS glow border around orb that flashes on high-intensity emotions
5. Render commentary text below orb with CSS typewriter reveal per sentence

### Dream: Option C (Custom GLSL Shader)

**Timeline:** 2-3 weeks
**What you get:** A fully custom visual experience that *is* the Arbiter — not a visualizer, but a living entity rendered in real-time on the GPU. Each emotion maps to a distinct visual world. The audience feels the AI's reactions physically. Nothing like it at any hackathon.

**If time is constrained:** Build Option A for the event, design Option C in parallel as a v2 enhancement.

---

## 8. Architecture Recommendation

Regardless of which visual approach is chosen, the underlying architecture should be:

```
Arbiter Backend (Python/FastAPI)
  → WebSocket broadcast: { type: "commentary", text: "...", emotion: "skeptical", intensity: 0.7 }
  → WebSocket broadcast: { type: "score_update", team: "...", score: 7.2, delta: +1.4 }
  → WebSocket broadcast: { type: "question", text: "...", emotion: "curious" }

React Frontend (audience display)
  → useWebSocket hook: receives events
  → Emotion state machine: current emotion + transition history
  → Animation layer: orb/shader/character driven by state
  → Content layer: commentary text, score display, team info
  → Event flash layer: CSS/GSAP triggered bursts on significant moments
```

The emotion state machine should maintain:
- `currentEmotion`: the active emotion tag
- `previousEmotion`: for transition effects
- `intensity`: 0.0–1.0 from the backend
- `sessionIntensity`: rolling average for ambient background level

---

## Sources

- [GitHub Universe 2024 Production — JNSQ Agency](https://www.jnsq.agency/our-work/github-universe-2024)
- [GitHub Copilot CLI ASCII Animation Engineering](https://github.blog/engineering/from-pixels-to-characters-the-engineering-behind-github-copilot-clis-animated-ascii-banner/)
- [ElevenLabs Orb Component Documentation](https://ui.elevenlabs.io/docs/components/orb)
- [ElevenLabs UI Open Source Repo](https://github.com/elevenlabs/ui)
- [Open-LLM-VTuber — LLM to Live2D emotion pipeline](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)
- [kopiro/siriwave — Apple Siri waveform in JS](https://github.com/kopiro/siriwave)
- [Rive State Machine Overview](https://help.rive.app/editor/state-machine)
- [Integrating Rive into React — Codrops](https://tympanus.net/codrops/2025/05/12/integrating-rive-into-a-react-project-behind-the-scenes-of-valley-adventures/)
- [GSAP MorphSVG Plugin](https://gsap.com/docs/v3/Plugins/MorphSVGPlugin/)
- [Building Efficient Three.js Scenes — Codrops](https://tympanus.net/codrops/2025/02/11/building-efficient-three-js-scenes-optimize-performance-while-maintaining-quality/)
- [react-particles-webgl — React Three Fiber particle library](https://github.com/tim-soft/react-particles-webgl)
- [High-Performance Web Animation: GSAP, WebGL, 60fps — DEV Community](https://dev.to/kolonatalie/high-performance-web-animation-gsap-webgl-and-the-secret-to-60fps-2l1g)
- [Building a Voice Reactive Orb in React — Medium](https://medium.com/@therealmilesjackson/building-a-voice-reactive-orb-in-react-audio-visualization-for-voice-assistants-2bee12797b93)
- [Spotify Wrapped 2024 Design Analysis — Medium](https://medium.com/designright/three-design-elements-that-made-spotify-wrapped-2024-great-0a8e2b133b72)
- [WebSocket-Controlled State Machine — End Point Dev](https://www.endpointdev.com/blog/2024/07/websocket-controlled-state-machine/)
- [GSAP vs Framer Motion Comparison — Semaphore](https://semaphore.io/blog/react-framer-motion-gsap)
- [Live2D Cubism](https://www.live2d.com/en/)
- [L of L 2024 World Championship Remote Production — SVG Europe](https://www.svgeurope.org/blog/headlines/tech-eye-view-inside-the-epic-remote-production-for-riot-games-league-of-legends-world-championships-finals-2024/)
