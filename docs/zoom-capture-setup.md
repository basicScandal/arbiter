# Zoom Capture Setup -- BlackHole + OBS Virtual Camera

## Overview

Route Zoom demo audio and video into Arbiter's capture pipeline without code changes.
Zoom audio passes through BlackHole (virtual audio loopback) to PyAudio.
Zoom video passes through OBS Virtual Camera to OpenCV.

```
Zoom app
  ├── audio → BlackHole → PyAudio (AUDIO_DEVICE_INDEX)
  └── video → OBS Window Capture → Virtual Camera → OpenCV (CAMERA_DEVICE_INDEX)
```

## Prerequisites

| Tool | Install | Purpose |
|------|---------|---------|
| [BlackHole](https://existential.audio/blackhole/) | `brew install blackhole-2ch` | Virtual audio loopback |
| [OBS Studio](https://obsproject.com/) | `brew install --cask obs` | Virtual camera from window capture |

## Audio Setup (BlackHole)

### 1. Install BlackHole

```bash
brew install blackhole-2ch
```

### 2. Create Multi-Output Device

This lets you hear Zoom audio *and* route it to Arbiter simultaneously.

1. Open **Audio MIDI Setup** (`/Applications/Utilities/Audio MIDI Setup.app`)
2. Click **+** (bottom-left) > **Create Multi-Output Device**
3. Check both:
   - Your real speakers/headphones
   - **BlackHole 2ch**
4. Right-click the Multi-Output Device > **Use This Device For Sound Output**

### 3. Set Zoom audio output

In Zoom > **Settings > Audio > Speaker**, select **Multi-Output Device**.
This ensures Zoom audio goes to both your speakers and BlackHole.

### TTS feedback prevention

Arbiter already handles this. When TTS speaks, the capture pipeline mutes audio input
(`src/capture/pipeline.py:243-251`) to prevent the judge's own voice from being
re-captured. No additional configuration needed.

## Video Setup (OBS Virtual Camera)

### 1. Install OBS

```bash
brew install --cask obs
```

### 2. Configure a Window Capture scene

1. Launch OBS
2. In **Sources**, click **+** > **Window Capture**
3. Select the Zoom meeting window
4. Crop/resize to frame the demo content (presenter's shared screen)

### 3. Start Virtual Camera

1. Click **Start Virtual Camera** in OBS (bottom-right)
2. OBS must be running with Virtual Camera active *before* starting Arbiter

## Device Discovery

Find the correct device indices for your `.env` file.

### Audio devices

```bash
uv run python -c "
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    d = p.get_device_info_by_index(i)
    if d['maxInputChannels'] > 0:
        print(f'  [{i}] {d[\"name\"]}')
p.terminate()
"
```

Look for `BlackHole 2ch` in the output. Note its index number.

### Video devices

```bash
uv run python -c "
import cv2
for i in range(10):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f'  [{i}] Camera device (open OK)')
        cap.release()
"
```

The OBS Virtual Camera typically appears as the last device. Note its index number.

## Configuration

Set both indices in your `.env` file:

```bash
# Example -- replace with your actual device indices
AUDIO_DEVICE_INDEX=2    # BlackHole 2ch
CAMERA_DEVICE_INDEX=1   # OBS Virtual Camera
```

## Verification

### 1. Check startup logs

Start Arbiter and confirm the correct devices are selected:

```bash
uv run arbiter
```

You should see:
```
Starting audio capture: 16000Hz, 1 channels, chunk_size=512, device=2
Starting camera capture on device 1 at 1.0 FPS
```

If the camera device can't be opened, you'll see:
```
Cannot open camera device 1. Check that the device is connected and not in use by another application.
```

This means OBS Virtual Camera is not started or the index is wrong.

### 2. Test with a Zoom call

1. Join a Zoom test meeting (or call yourself from another device)
2. Start a demo from the operator dashboard
3. Verify observations appear in the vitals panel (confirms video is flowing)
4. Verify transcripts appear (confirms audio is flowing)

## Troubleshooting

### No audio captured

1. **Wrong device index** -- Re-run the audio discovery script and verify the BlackHole index
2. **Multi-Output not set** -- Confirm system sound output is set to the Multi-Output Device (System Settings > Sound > Output)
3. **Zoom output not set** -- Confirm Zoom is outputting to Multi-Output Device, not just system default
4. **BlackHole not installed** -- Run `brew list blackhole-2ch` to verify

### No video captured

1. **OBS Virtual Camera not started** -- Check OBS shows "Stop Virtual Camera" (meaning it's active)
2. **Wrong device index** -- Re-run the video discovery script
3. **OBS not capturing Zoom** -- Verify the OBS preview shows the Zoom window content
4. **Permission denied** -- macOS may prompt for camera permissions on first use; grant them to Python/Terminal

### Audio feedback loop

This should not happen because Arbiter mutes audio capture during TTS playback.
If you hear feedback:

1. Confirm Arbiter is running the latest code (TTS mute was added in the pipeline)
2. Check that Zoom isn't echoing TTS back -- mute Arbiter's mic in Zoom if using bidirectional audio
3. As a last resort, lower system volume during TTS playback

## Fallback: Direct Microphone

If BlackHole setup fails or isn't available:

1. Place a physical microphone near the speakers playing Zoom audio
2. Set `AUDIO_DEVICE_INDEX` to that microphone's index (or leave unset for system default)
3. This works but captures ambient noise and may miss quiet audio

For video fallback, point a physical camera at the screen displaying the Zoom demo
and set `CAMERA_DEVICE_INDEX` to that camera's index.
