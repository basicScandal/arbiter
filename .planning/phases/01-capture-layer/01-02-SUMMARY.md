---
phase: 01-capture-layer
plan: 02
subsystem: capture
tags: [opencv, pyaudio, asyncio, pillow, numpy, key-frames, histogram]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Pydantic data models (FrameData, MediaChunk, CaptureEvent subclasses), CaptureConfig, EventBus, async patterns"
provides:
  - "CameraCapture: async frame capture with JPEG encoding, thumbnailing, key frame detection, and event publishing"
  - "AudioCapture: async microphone PCM capture with mute/unmute API and queue-based output"
  - "KeyFrameDetector: histogram-based scene change detection for identifying significant visual changes"
affects: [01-03-PLAN, 01-04-PLAN, 02-defense-pipeline, 03-commentary-engine]

# Tech tracking
tech-stack:
  added: []
  patterns: [asyncio-to-thread-wrapping, bounded-queue-overflow-drop, histogram-scene-change]

key-files:
  created:
    - src/capture/camera.py
    - src/capture/audio.py
    - src/capture/key_frames.py
  modified: []

key-decisions:
  - "KeyFrameDetector uses cv2.HISTCMP_CORREL with threshold 0.4 for scene change detection"
  - "Camera _capture_and_encode is synchronous, called via asyncio.to_thread for non-blocking capture"
  - "Audio mute discards data but keeps reading the stream to prevent buffer overflow"

patterns-established:
  - "Blocking I/O wrapping: all OpenCV and PyAudio calls go through asyncio.to_thread()"
  - "Queue overflow: both producers use put_nowait with QueueFull exception handling (silent drop)"
  - "Capture lifecycle: run() loops until stop_event is set, stop() sets event and cleans up"

# Metrics
duration: 2min
completed: 2026-02-15
---

# Phase 1 Plan 02: Camera and Audio Capture Summary

**Async camera capture with JPEG thumbnailing and histogram key frame detection, plus PCM microphone capture with mute/unmute for echo prevention**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-16T05:37:02Z
- **Completed:** 2026-02-16T05:39:09Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Built CameraCapture with async frame capture at ~1 FPS, BGR-to-RGB conversion, PIL thumbnailing to 1024x1024, JPEG encoding, and base64 output
- Built KeyFrameDetector using OpenCV histogram correlation to identify significant visual changes (slide transitions, screen switches)
- Built AudioCapture for 16-bit PCM at 16kHz mono with mute/unmute API for downstream echo prevention
- All blocking I/O (OpenCV cap.read, PyAudio stream.read/open) wrapped in asyncio.to_thread()
- Both producers publish events to EventBus and use bounded queues with graceful overflow handling

## Task Commits

Each task was committed atomically:

1. **Task 1: Camera frame capture and key frame detection** - `e376639` (feat)
2. **Task 2: Audio microphone capture with mute/unmute** - `a331eba` (feat)

## Files Created/Modified
- `src/capture/key_frames.py` - KeyFrameDetector class: histogram-based scene change detection with configurable threshold
- `src/capture/camera.py` - CameraCapture class: async frame capture, JPEG encode, thumbnail, event publish, queue output
- `src/capture/audio.py` - AudioCapture class: async PCM microphone capture with mute/unmute, queue output

## Decisions Made
- KeyFrameDetector uses grayscale histogram correlation (cv2.HISTCMP_CORREL) -- values below 0.4 threshold indicate scene change. Simple, fast (<1ms per comparison), sufficient for slide transitions
- Camera's _capture_and_encode is a synchronous method called through asyncio.to_thread(), keeping all OpenCV blocking I/O off the event loop while bundling read+encode+thumbnail in one thread call
- Audio mute implementation keeps reading from the stream (discards data) rather than pausing the stream, preventing PyAudio buffer overflow and keeping the stream alive for fast unmute

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. Camera and microphone hardware access will be needed at runtime.

## Next Phase Readiness
- Camera and audio producers are ready for Plan 03 (Gemini session management) to consume from the shared output queue
- Plan 04 (orchestrator) can wire CameraCapture and AudioCapture into the demo lifecycle
- Mute/unmute API is ready for Phase 3 commentary engine to control during TTS playback
- No blockers for next plan

## Self-Check: PASSED

All 3 created files verified on disk (camera.py: 169 lines, audio.py: 132 lines, key_frames.py: 69 lines). Both task commits (e376639, a331eba) verified in git log. All minimum line counts met.

---
*Phase: 01-capture-layer*
*Completed: 2026-02-15*
