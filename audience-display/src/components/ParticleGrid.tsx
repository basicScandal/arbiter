import { useEffect, useRef } from "react";
import { useDisplayStore } from "../store/displayStore";
import { emotionConfig, defaultVisuals } from "../lib/emotionConfig";

interface Particle {
  x: number;
  y: number;
  baseX: number;
  baseY: number;
  vx: number;
  vy: number;
  size: number;
  opacity: number;
}

interface ParticleState {
  baseOpacity: number;
  driftSpeed: number;
  colorR: number;
  colorG: number;
  colorB: number;
  flowDirection: "idle" | "inward" | "outward" | "freeze" | "sink" | "vortex";
}

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function getParticleState(activeScreen: string, emotion?: string): ParticleState {
  const visuals =
    emotion && emotionConfig[emotion] ? emotionConfig[emotion] : defaultVisuals;
  const [r, g, b] = hexToRgb(visuals.secondary);

  switch (activeScreen) {
    case "thinking":
      return {
        baseOpacity: 0.35,
        driftSpeed: 1.2,
        colorR: 0,
        colorG: 212,
        colorB: 255,
        flowDirection: "inward",
      };
    case "commentary":
      return {
        baseOpacity: 0.2 + visuals.intensity * 0.15,
        driftSpeed: 0.3 + visuals.intensity * 0.5,
        colorR: r,
        colorG: g,
        colorB: b,
        flowDirection: "outward",
      };
    case "question":
      return {
        baseOpacity: 0.15,
        driftSpeed: 0.05,
        colorR: 255,
        colorG: 140,
        colorB: 0,
        flowDirection: "freeze",
      };
    case "scorecard":
      return {
        baseOpacity: 0.2,
        driftSpeed: 0.15,
        colorR: 255,
        colorG: 215,
        colorB: 0,
        flowDirection: "idle",
      };
    case "deliberation":
      return {
        baseOpacity: 0.25,
        driftSpeed: 0.4,
        colorR: 123,
        colorG: 97,
        colorB: 255,
        flowDirection: "vortex",
      };
    case "idle":
    case "intermission":
    default:
      return {
        baseOpacity: 0.12,
        driftSpeed: 0.15,
        colorR: 0,
        colorG: 212,
        colorB: 255,
        flowDirection: "idle",
      };
  }
}

const GRID_SPACING = 48;
const PARTICLE_SIZE = 2.5;
const RETURN_STRENGTH = 0.01;

export function ParticleGrid() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const stateRef = useRef<ParticleState>(getParticleState("idle"));
  const animRef = useRef<number>(0);
  const activeScreen = useDisplayStore((s) => s.activeScreen);
  const sentences = useDisplayStore((s) => s.commentarySentences);
  const latestEmotion =
    sentences.length > 0
      ? sentences[sentences.length - 1].emotion
      : undefined;

  // Update target state reactively
  useEffect(() => {
    stateRef.current = getParticleState(activeScreen, latestEmotion);
  }, [activeScreen, latestEmotion]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    function resize() {
      const dpr = window.devicePixelRatio || 1;
      canvas!.width = canvas!.clientWidth * dpr;
      canvas!.height = canvas!.clientHeight * dpr;
      ctx!.scale(dpr, dpr);
      initParticles();
    }

    function initParticles() {
      const w = canvas!.clientWidth;
      const h = canvas!.clientHeight;
      const particles: Particle[] = [];
      for (let x = GRID_SPACING; x < w; x += GRID_SPACING) {
        for (let y = GRID_SPACING; y < h; y += GRID_SPACING) {
          if (particles.length >= 200) break;
          particles.push({
            x,
            y,
            baseX: x,
            baseY: y,
            vx: 0,
            vy: 0,
            size: PARTICLE_SIZE,
            opacity: 0.12,
          });
        }
        if (particles.length >= 200) break;
      }
      particlesRef.current = particles;
    }

    resize();
    window.addEventListener("resize", resize);

    function animate() {
      const w = canvas!.clientWidth;
      const h = canvas!.clientHeight;
      const cx = w / 2;
      const cy = h / 2;
      ctx!.clearRect(0, 0, w, h);

      const s = stateRef.current;

      for (const p of particlesRef.current) {
        // Distance from center (sigil position)
        const dx = p.x - cx;
        const dy = p.y - cy;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;

        // Flow behavior
        switch (s.flowDirection) {
          case "inward": {
            // Drift toward center
            p.vx += (-dx / dist) * s.driftSpeed * 0.02;
            p.vy += (-dy / dist) * s.driftSpeed * 0.02;
            break;
          }
          case "outward": {
            // Gentle push outward
            p.vx += (dx / dist) * s.driftSpeed * 0.005;
            p.vy += (dy / dist) * s.driftSpeed * 0.005;
            break;
          }
          case "vortex": {
            // Circular orbit
            p.vx += (-dy / dist) * s.driftSpeed * 0.008;
            p.vy += (dx / dist) * s.driftSpeed * 0.008;
            break;
          }
          case "sink": {
            // Drift downward
            p.vy += 0.005 * s.driftSpeed;
            break;
          }
          case "freeze": {
            // Strong return to grid, minimal drift
            p.vx *= 0.9;
            p.vy *= 0.9;
            break;
          }
          case "idle":
          default: {
            // Gentle random drift
            p.vx += (Math.random() - 0.5) * s.driftSpeed * 0.01;
            p.vy += (Math.random() - 0.5) * s.driftSpeed * 0.01;
            break;
          }
        }

        // Return-to-grid spring force
        p.vx += (p.baseX - p.x) * RETURN_STRENGTH;
        p.vy += (p.baseY - p.y) * RETURN_STRENGTH;

        // Damping
        p.vx *= 0.96;
        p.vy *= 0.96;

        // Update position
        p.x += p.vx;
        p.y += p.vy;

        // Proximity glow — particles near center are brighter
        const proximityBoost = Math.max(0, 1 - dist / 300) * 0.2;

        // Lerp opacity toward target
        const targetOpacity = s.baseOpacity + proximityBoost;
        p.opacity += (targetOpacity - p.opacity) * 0.05;

        // Draw
        ctx!.beginPath();
        ctx!.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx!.fillStyle = `rgba(${s.colorR}, ${s.colorG}, ${s.colorB}, ${p.opacity})`;
        ctx!.fill();
      }

      animRef.current = requestAnimationFrame(animate);
    }

    animRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none"
      style={{ zIndex: -1 }}
    />
  );
}
