import { useEffect, useRef } from "react";
import { useOperatorStore } from "../store/operatorStore";

let audioCtx: AudioContext | null = null;

function getAudioContext(): AudioContext {
  if (!audioCtx) audioCtx = new AudioContext();
  return audioCtx;
}

function playTone(freq: number, duration = 0.15, volume = 0.08) {
  try {
    const ctx = getAudioContext();
    if (ctx.state === "suspended") ctx.resume();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = freq;
    osc.type = "sine";
    gain.gain.setValueAtTime(volume, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  } catch {
    // Audio not available — silently ignore
  }
}

const TONES = {
  start: () => playTone(440, 0.2, 0.1),
  stop: () => playTone(330, 0.25, 0.08),
  stateChange: () => playTone(660, 0.1, 0.06),
  injection: () => playTone(220, 0.3, 0.1),
  commentary: () => playTone(880, 0.08, 0.05),
  judgmentStart: () => {
    // Subtle ascending two-tone: signals "judgment has begun"
    playTone(392, 0.15, 0.07);  // G4
    setTimeout(() => playTone(494, 0.2, 0.08), 160);  // B4
  },
  score: () => {
    playTone(523, 0.15, 0.08);
    setTimeout(() => playTone(659, 0.15, 0.08), 150);
    setTimeout(() => playTone(784, 0.2, 0.1), 300);
  },
};

/**
 * Reactive audio feedback hook. Subscribes to store changes and plays
 * subtle Web Audio API tones for key events. Respects muted state.
 */
export function useAudioFeedback(muted: boolean) {
  const prevState = useRef<string>("idle");
  const prevEventCount = useRef<number>(0);

  useEffect(() => {
    if (muted) return;

    const unsub = useOperatorStore.subscribe((state) => {
      // State change tones
      if (state.demoState !== prevState.current) {
        const newState = state.demoState;
        const oldState = prevState.current;
        prevState.current = newState;

        if (newState === "capturing" && oldState === "idle") TONES.start();
        else if (newState === "stopped") TONES.stop();
        else TONES.stateChange();
      }

      // New event tones
      if (state.events.length > prevEventCount.current && state.events.length > 0) {
        const latest = state.events[0];
        if (latest.event_type === "injection_detected") TONES.injection();
        else if (latest.event_type === "observation_verified") TONES.judgmentStart();
        else if (latest.event_type === "commentary_delivered") TONES.commentary();
        else if (latest.event_type === "scoring_complete") TONES.score();
      }
      prevEventCount.current = state.events.length;
    });

    return unsub;
  }, [muted]);
}
