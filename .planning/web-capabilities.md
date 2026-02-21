# Web Frontend Capabilities for Sci-Fi Dashboard UI

**Research Date:** 2026-02-17
**Target:** React web operator dashboard at `/operator` (port 8080)
**Stack:** React 19, TypeScript, Vite, Tailwind CSS, Zustand, Framer Motion
**Location:** `operator-dashboard/` directory
**WebSocket:** `/ws/operator` (state updates, events, counter ticks, commands)

---

## 1. Framer Motion Animation System

### Core Capabilities

Motion (formerly Framer Motion) is the leading React animation library with 30.7k GitHub stars and 3.6M weekly npm downloads.

**Basic Animation Example:**
```tsx
import { motion } from 'framer-motion';

function AgentCard() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
    >
      Agent Status
    </motion.div>
  );
}
```

### Variants & Orchestration

Variants enable complex animation choreography:

```tsx
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.3
    }
  }
};

const itemVariants = {
  hidden: { opacity: 0, x: -20 },
  visible: { opacity: 1, x: 0 }
};

function AgentList() {
  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {agents.map(agent => (
        <motion.div key={agent.id} variants={itemVariants}>
          {agent.name}
        </motion.div>
      ))}
    </motion.div>
  );
}
```

**Orchestration Features:**
- `staggerChildren: 0.2` - Delay between each child animation (seconds)
- `delayChildren: 0.3` - Delay before children start
- `beforeChildren` - Parent animates before children
- `afterChildren` - Parent animates after children

### Scroll Animations

```tsx
import { useScroll, useTransform, motion } from 'framer-motion';

function ParallaxSection() {
  const { scrollYProgress } = useScroll();

  const y = useTransform(scrollYProgress, [0, 1], [0, -100]);
  const opacity = useTransform(scrollYProgress, [0, 0.5, 1], [1, 0.5, 0]);

  return (
    <motion.div style={{ y, opacity }}>
      Parallax Content
    </motion.div>
  );
}
```

**useScroll Returns:**
- `scrollX`, `scrollY` - Absolute scroll position
- `scrollXProgress`, `scrollYProgress` - 0 to 1 progress

### Layout Animations

Shared element transitions between states:

```tsx
function ExpandableCard({ isExpanded, onClick }) {
  return (
    <motion.div
      layout
      layoutId="agent-card-1"
      onClick={onClick}
      style={{
        width: isExpanded ? 500 : 200,
        height: isExpanded ? 400 : 100
      }}
    >
      Content
    </motion.div>
  );
}
```

**Key:** `layout` prop + `layoutId` for shared animations.

### Performance

Always animate transforms for GPU acceleration:
- ✅ `x`, `y`, `scale`, `rotate`, `opacity`
- ❌ `width`, `height`, `top`, `left` (causes reflow)

---

## 2. CSS Advanced Effects

### Backdrop Filter (Frosted Glass)

Perfect for sci-fi overlays:

```css
.glass-panel {
  background: rgba(17, 25, 40, 0.75);
  backdrop-filter: blur(12px) saturate(150%);
  border: 1px solid rgba(255, 255, 255, 0.125);
  border-radius: 12px;
}

/* Dark theme enhancement */
.glass-panel-dark {
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(16px) brightness(80%) saturate(120%);
}
```

**Available Filters:**
- `blur(px)` - Gaussian blur
- `brightness(%)` - Lighten/darken
- `contrast(%)` - Adjust contrast
- `saturate(%)` - Color intensity
- `hue-rotate(deg)` - Shift colors
- `grayscale(%)` - Desaturation

**Browser Support:** All modern browsers (Chrome, Edge, Safari, Firefox 103+)

### CSS Keyframes & Animations

```css
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(1.05); }
}

@keyframes scanline {
  0% { transform: translateY(-100%); }
  100% { transform: translateY(100%); }
}

.agent-active {
  animation: pulse 2s ease-in-out infinite;
}

.hud-scan {
  animation: scanline 3s linear infinite;
}
```

### Staggered Animations

```css
.stat-card:nth-child(1) { animation-delay: 0s; }
.stat-card:nth-child(2) { animation-delay: 0.1s; }
.stat-card:nth-child(3) { animation-delay: 0.2s; }
.stat-card:nth-child(4) { animation-delay: 0.3s; }

/* Or use calc() for dynamic stagger */
.item {
  animation: slideIn 0.5s ease-out backwards;
  animation-delay: calc(var(--index) * 0.1s);
}
```

### CSS Custom Properties (Theming)

```css
@layer theme {
  :root {
    --color-primary: #00ffff;
    --color-secondary: #ff00ff;
    --color-accent: #00ff88;
    --glow-intensity: 0.8;
  }

  .dark-theme {
    --bg-primary: #0a0e14;
    --bg-secondary: #1a1f2e;
    --text-primary: #e6e6e6;
  }
}

.neon-text {
  color: var(--color-primary);
  text-shadow: 0 0 10px var(--color-primary);
  filter: brightness(var(--glow-intensity));
}
```

---

## 3. Tailwind CSS with Dark Theme

### Tailwind v4 Approach (2026)

```css
@import "tailwindcss";

@theme {
  --color-cyber-cyan: #00ffff;
  --color-cyber-magenta: #ff00ff;
  --color-neon-green: #00ff88;

  --radius-lg: 12px;
  --shadow-glow: 0 0 20px rgba(0, 255, 255, 0.5);
}

@utility backdrop-blur-glass {
  backdrop-filter: blur(12px) saturate(150%);
}
```

### Dynamic Theme Switching

```tsx
function ThemeProvider({ children }) {
  const [theme, setTheme] = useState('dark');

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  return <>{children}</>;
}
```

### Tailwind Class Examples

```tsx
<div className="
  bg-black/80
  backdrop-blur-xl
  border border-cyan-500/30
  rounded-lg
  shadow-[0_0_20px_rgba(0,255,255,0.3)]
  hover:shadow-[0_0_30px_rgba(0,255,255,0.5)]
  transition-shadow duration-300
">
  Glass Panel
</div>
```

---

## 4. WebGL & Three.js with React Three Fiber

### React Three Fiber Basics

```tsx
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Environment } from '@react-three/drei';

function Scene3D() {
  return (
    <Canvas camera={{ position: [0, 0, 5] }}>
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} />

      <mesh>
        <sphereGeometry args={[1, 32, 32]} />
        <meshStandardMaterial color="#00ffff" emissive="#0088ff" />
      </mesh>

      <OrbitControls />
      <Environment preset="city" />
    </Canvas>
  );
}
```

### 3D Data Visualization

Perfect for agent status displays:

```tsx
function AgentVisualization({ agents }) {
  return (
    <Canvas>
      {agents.map((agent, i) => (
        <mesh key={agent.id} position={[i * 2, 0, 0]}>
          <cylinderGeometry args={[0.5, 0.5, agent.score / 10]} />
          <meshStandardMaterial
            color={agent.active ? '#00ff88' : '#444'}
            emissive={agent.active ? '#00ff88' : '#000'}
            emissiveIntensity={0.5}
          />
        </mesh>
      ))}
    </Canvas>
  );
}
```

### Performance with WebGPU (2026)

Three.js now supports WebGPU for enhanced performance:
- Faster frame rates
- Improved lighting accuracy
- Reduced GPU load
- Better TypeScript support

---

## 5. D3.js for Data Visualization

### Real-Time WebSocket Integration

```tsx
import * as d3 from 'd3';
import { useEffect, useRef } from 'react';

function LiveChart({ data }) {
  const svgRef = useRef();

  useEffect(() => {
    const svg = d3.select(svgRef.current);

    // Scales
    const xScale = d3.scaleLinear()
      .domain([0, data.length])
      .range([0, 400]);

    const yScale = d3.scaleLinear()
      .domain([0, d3.max(data)])
      .range([200, 0]);

    // Line generator
    const line = d3.line()
      .x((d, i) => xScale(i))
      .y(d => yScale(d))
      .curve(d3.curveMonotoneX);

    // Update path with transition
    svg.select('.line')
      .datum(data)
      .transition()
      .duration(300)
      .attr('d', line);

  }, [data]);

  return (
    <svg ref={svgRef} width={400} height={200}>
      <path className="line" fill="none" stroke="#00ffff" strokeWidth={2} />
    </svg>
  );
}
```

### WebSocket + D3 Pattern

```tsx
function RealtimeDashboard() {
  const [data, setData] = useState([]);
  const ws = useRef<WebSocket>();

  useEffect(() => {
    ws.current = new WebSocket('ws://localhost:8080/ws/operator');

    ws.current.onmessage = (event) => {
      const newData = JSON.parse(event.data);
      setData(prev => [...prev.slice(-50), newData.value]);
    };

    return () => ws.current?.close();
  }, []);

  return <LiveChart data={data} />;
}
```

---

## 6. Web Audio API Integration

### Audio Visualization

```tsx
function AudioVisualizer() {
  const analyserRef = useRef<AnalyserNode>();
  const dataArrayRef = useRef<Uint8Array>();

  useEffect(() => {
    const audioContext = new AudioContext();
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;

    analyserRef.current = analyser;
    dataArrayRef.current = new Uint8Array(analyser.frequencyBinCount);

    // Connect to audio source
    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);

    // Animation loop
    function draw() {
      analyser.getByteFrequencyData(dataArrayRef.current);
      // Render bars based on dataArrayRef.current
      requestAnimationFrame(draw);
    }
    draw();
  }, []);
}
```

### Reactive Sound Design

```tsx
function SoundFeedback({ eventType }) {
  const playSound = useCallback((type: string) => {
    const audioContext = new AudioContext();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);

    // Sci-fi beep frequencies
    const frequencies = {
      agentActive: 880,
      agentComplete: 1320,
      error: 220
    };

    oscillator.frequency.value = frequencies[type];
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);

    oscillator.start();
    oscillator.stop(audioContext.currentTime + 0.3);
  }, []);

  useEffect(() => {
    playSound(eventType);
  }, [eventType]);
}
```

---

## 7. Zustand State Management

### WebSocket Integration Pattern

```tsx
import create from 'zustand';

interface DashboardStore {
  agents: Agent[];
  events: Event[];
  connected: boolean;
  ws: WebSocket | null;
  connect: () => void;
  updateAgent: (id: string, data: Partial<Agent>) => void;
}

const useDashboardStore = create<DashboardStore>((set, get) => ({
  agents: [],
  events: [],
  connected: false,
  ws: null,

  connect: () => {
    const ws = new WebSocket('ws://localhost:8080/ws/operator');

    ws.onopen = () => set({ connected: true, ws });

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'agent_update') {
        set(state => ({
          agents: state.agents.map(a =>
            a.id === data.id ? { ...a, ...data.payload } : a
          )
        }));
      }
    };

    ws.onclose = () => set({ connected: false, ws: null });
  },

  updateAgent: (id, data) => set(state => ({
    agents: state.agents.map(a => a.id === id ? { ...a, ...data } : a)
  }))
}));
```

### Usage in Components

```tsx
function AgentCard({ agentId }) {
  const agent = useDashboardStore(state =>
    state.agents.find(a => a.id === agentId)
  );

  return <div>{agent?.name}: {agent?.status}</div>;
}
```

---

## 8. React 19 + TypeScript + Vite

### Best Practices (2026)

**Vite Configuration:**
```ts
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc'; // 40x faster than CRA

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true
      }
    }
  }
});
```

**React 19 Features:**
- `useActionState` - Form handling
- `useFormStatus` - Form submission state
- `useOptimistic` - Optimistic UI updates
- `use()` API - Resource fetching

**TypeScript Patterns:**
```tsx
interface AgentState {
  id: string;
  name: string;
  status: 'idle' | 'thinking' | 'responding' | 'complete';
  score: number;
}

type AgentAction =
  | { type: 'START'; id: string }
  | { type: 'UPDATE_SCORE'; id: string; score: number }
  | { type: 'COMPLETE'; id: string };
```

---

## 9. Sci-Fi UI Design Resources

### Frameworks & Kits

**Arwes** - Futuristic Sci-Fi UI Web Framework
- Dark aesthetic with neon accents
- Built-in animation systems
- Sound effects integration
- Active development (v1.0.0-alpha.23)
- GitHub: https://github.com/arwes/arwes

**Dynamic SciFi Dashboard Kit**
Components:
- `KeyValueListPanel` - Data tables
- `LedDisplayPanel` - LED-style text
- `DynamicTextPanel` - Typewriter effects
- `CircularGaugePanel` - Radial progress

### Design Characteristics

**Color Schemes:**
- Primary: Cyan (#00ffff), Magenta (#ff00ff)
- Accent: Neon green (#00ff88)
- Background: Very dark blue/black (#0a0e14)

**Typography:**
- Monospace fonts for data
- Sans-serif for UI elements
- Large size contrast for hierarchy

**Visual Effects:**
- Glow/bloom on active elements
- Scanline animations
- Grid patterns in backgrounds
- Holographic shimmer effects

**Layout Patterns:**
- Asymmetrical compositions
- Layered panels with depth
- Angular shapes and diagonal lines
- Data-dense displays

---

## 10. Performance Optimization

### Animation Performance

```tsx
// ✅ Good - GPU accelerated
<motion.div style={{ x: 100, y: 50, scale: 1.2 }} />

// ❌ Bad - Causes layout thrashing
<motion.div style={{ width: 200, marginLeft: 50 }} />
```

### Code Splitting

```tsx
import { lazy, Suspense } from 'react';

const Chart3D = lazy(() => import('./Chart3D'));

function Dashboard() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <Chart3D data={data} />
    </Suspense>
  );
}
```

### WebSocket Optimization

```tsx
// Debounce rapid updates
import { useDebouncedCallback } from 'use-debounce';

const handleUpdate = useDebouncedCallback((data) => {
  updateStore(data);
}, 100);
```

---

## 11. Recommended Architecture

```
operator-dashboard/
├── src/
│   ├── components/
│   │   ├── agents/
│   │   │   ├── AgentCard.tsx
│   │   │   ├── AgentGrid.tsx
│   │   │   └── AgentDetail.tsx
│   │   ├── visualizations/
│   │   │   ├── ScoreChart.tsx
│   │   │   ├── ActivityGraph.tsx
│   │   │   └── 3DVisualization.tsx
│   │   └── ui/
│   │       ├── GlassPanel.tsx
│   │       ├── NeonButton.tsx
│   │       └── ScanlineEffect.tsx
│   ├── stores/
│   │   └── dashboardStore.ts (Zustand)
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   ├── useAudioFeedback.ts
│   │   └── useRealtimeData.ts
│   ├── styles/
│   │   └── theme.css (Tailwind + custom)
│   └── types/
│       └── dashboard.ts
```

---

## Sources

1. [Motion Documentation](https://motion.dev)
2. [Framer Motion Variants](https://www.framer.com/motion/transition/)
3. [Framer Motion Scroll](https://motion.dev/docs/react-scroll-animations)
4. [React Three Fiber](https://github.com/pmndrs/react-three-fiber)
5. [D3.js Real-Time](https://medium.com/@mantutorcodes/real-time-data-visualization-with-websockets-and-d3-js-97f74dd68994)
6. [Web Audio Visualization](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Visualizations_with_Web_Audio_API)
7. [Backdrop Filter](https://www.joshwcomeau.com/css/backdrop-filter/)
8. [Tailwind v4 Theming](https://medium.com/render-beyond/build-a-flawless-multi-theme-ui-using-new-tailwind-css-v4-react-dca2b3c95510)
9. [Zustand WebSockets](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/view)
10. [React 19 Best Practices](https://www.patterns.dev/react/react-2026/)
11. [Arwes Framework](https://arwes.dev/)
12. [Sci-Fi Dashboard Kit](https://www.cssscript.com/dynamic-scifi-dashboard/)
13. [CSS Animations 2026](https://devtoolbox.dedyn.io/blog/css-animations-complete-guide)
14. [Staggered Animations](https://medium.com/@onifkay/creating-staggered-animations-with-framer-motion-0e7dc90eae33)
15. [WebGL 2026 Updates](https://www.utsubo.com/blog/threejs-2026-what-changed)
