#!/usr/bin/env python3
"""Pre-event smoke test — validates hardware, API keys, and pipeline before going live.

Runs a series of checks and reports pass/fail for each. Exits with code 0 if
all critical checks pass, 1 if any critical check fails.

Usage:
    uv run python scripts/pre_event_smoke.py
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import time

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"

results: list[tuple[str, bool, str]] = []


def check(name: str, critical: bool = True):
    """Decorator to register a check function."""
    def decorator(fn):
        fn._check_name = name
        fn._critical = critical
        return fn
    return decorator


def report(name: str, passed: bool, detail: str = "", critical: bool = True):
    tag = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    crit = f" {RED}(CRITICAL){RESET}" if not passed and critical else ""
    print(f"  {tag} {name}{crit}")
    if detail:
        print(f"       {DIM}{detail}{RESET}")
    results.append((name, passed, "critical" if critical else "optional"))


# ---------------------------------------------------------------------------
# Environment / API key checks
# ---------------------------------------------------------------------------

def check_api_keys():
    print(f"\n{BOLD}API Keys{RESET}")
    keys = {
        "GEMINI_API_KEY": True,
        "ANTHROPIC_API_KEY": True,
        "CARTESIA_API_KEY": False,
        "OPENAI_API_KEY": False,
        "GROQ_API_KEY": False,
    }
    for key, critical in keys.items():
        val = os.environ.get(key, "")
        if val:
            report(key, True, f"{len(val)} chars", critical)
        else:
            report(key, False, "not set", critical)


# ---------------------------------------------------------------------------
# Software dependency checks
# ---------------------------------------------------------------------------

def check_dependencies():
    print(f"\n{BOLD}Dependencies{RESET}")

    # Python version
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 11
    report("Python 3.11+", ok, f"{v.major}.{v.minor}.{v.micro}")

    # Tesseract OCR
    tess = shutil.which("tesseract")
    if tess:
        try:
            ver = subprocess.check_output(
                ["tesseract", "--version"], stderr=subprocess.STDOUT, timeout=5
            ).decode().split("\n")[0]
            report("Tesseract OCR", True, ver)
        except Exception as e:
            report("Tesseract OCR", False, str(e))
    else:
        report("Tesseract OCR", False, "not found in PATH")

    # Frontend builds
    from pathlib import Path
    audience = Path("audience-display/dist/index.html")
    operator = Path("operator-dashboard/dist/index.html")
    report("Audience display build", audience.exists(),
           str(audience) if audience.exists() else "run: cd audience-display && bun run build")
    report("Operator dashboard build", operator.exists(),
           str(operator) if operator.exists() else "run: cd operator-dashboard && bun run build")


# ---------------------------------------------------------------------------
# Hardware checks
# ---------------------------------------------------------------------------

def check_camera():
    print(f"\n{BOLD}Camera{RESET}")
    try:
        import cv2
        idx = int(os.environ.get("CAMERA_DEVICE_INDEX", "0"))
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                report("Camera capture", True, f"device {idx}, {w}x{h}")
            else:
                report("Camera capture", False, f"device {idx} opened but no frame")
        else:
            report("Camera capture", False, f"device {idx} failed to open")
    except ImportError:
        report("Camera capture", False, "opencv-python not installed")
    except Exception as e:
        report("Camera capture", False, str(e))


def check_audio():
    print(f"\n{BOLD}Audio{RESET}")
    try:
        import pyaudio
        pya = pyaudio.PyAudio()
        idx = int(os.environ.get("AUDIO_DEVICE_INDEX", "0"))
        count = pya.get_device_count()
        report("Audio devices found", count > 0, f"{count} devices")

        if idx < count:
            info = pya.get_device_info_by_index(idx)
            name = info.get("name", "unknown")
            channels = int(info.get("maxInputChannels", 0))
            report(f"Audio device {idx}", channels > 0,
                   f"{name} ({channels} input channels)")
        else:
            report(f"Audio device {idx}", False,
                   f"index {idx} out of range (max {count - 1})")

        pya.terminate()
    except ImportError:
        report("Audio (PyAudio)", False, "pyaudio not installed")
    except Exception as e:
        report("Audio", False, str(e))


def check_blackhole():
    """Check for BlackHole virtual audio loopback (macOS Zoom capture)."""
    print(f"\n{BOLD}BlackHole (optional — for Zoom){RESET}")
    try:
        import pyaudio
        pya = pyaudio.PyAudio()
        found = False
        for i in range(pya.get_device_count()):
            info = pya.get_device_info_by_index(i)
            if "blackhole" in info.get("name", "").lower():
                report("BlackHole device", True, f"index {i}: {info['name']}", critical=False)
                found = True
                break
        if not found:
            report("BlackHole device", False, "not found — only needed for Zoom demos", critical=False)
        pya.terminate()
    except Exception:
        report("BlackHole device", False, "pyaudio not available", critical=False)


# ---------------------------------------------------------------------------
# API connectivity checks
# ---------------------------------------------------------------------------

async def check_gemini_api():
    print(f"\n{BOLD}Gemini API{RESET}")
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        report("Gemini API call", False, "no API key")
        return
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        start = time.monotonic()
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents="Reply with exactly: OK",
                config=types.GenerateContentConfig(
                    max_output_tokens=10,
                    temperature=0.0,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            ),
            timeout=15.0,
        )
        elapsed = time.monotonic() - start
        text = (response.text or "").strip()[:50]
        report("Gemini API call", True, f"{elapsed:.1f}s — response: {text!r}")
    except Exception as e:
        report("Gemini API call", False, str(e)[:100])


async def check_anthropic_api():
    print(f"\n{BOLD}Claude API{RESET}")
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        report("Claude API call", False, "no API key", critical=False)
        return
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=key)
        start = time.monotonic()
        msg = await asyncio.wait_for(
            client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=10,
                messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            ),
            timeout=15.0,
        )
        elapsed = time.monotonic() - start
        text = msg.content[0].text.strip()[:50] if msg.content else ""
        report("Claude API call", True, f"{elapsed:.1f}s — response: {text!r}", critical=False)
    except Exception as e:
        report("Claude API call", False, str(e)[:100], critical=False)


# ---------------------------------------------------------------------------
# Data directory checks
# ---------------------------------------------------------------------------

def check_data_dirs():
    print(f"\n{BOLD}Data Directories{RESET}")
    from pathlib import Path
    dirs = ["data/scores", "data/observations", "data/human_scores", "data/deliberation"]
    for d in dirs:
        p = Path(d)
        p.mkdir(parents=True, exist_ok=True)
        writable = os.access(p, os.W_OK)
        report(f"{d}/", writable, "writable" if writable else "NOT writable")


# ---------------------------------------------------------------------------
# Port check
# ---------------------------------------------------------------------------

def check_port():
    print(f"\n{BOLD}Port 8080{RESET}")
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("0.0.0.0", 8080))
        sock.close()
        report("Port 8080 available", True)
    except OSError:
        report("Port 8080 available", False, "already in use — is arbiter already running?")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print(f"\n{BOLD}{'='*50}")
    print("  ARBITER Pre-Event Smoke Test")
    print(f"{'='*50}{RESET}")

    check_api_keys()
    check_dependencies()
    check_camera()
    check_audio()
    check_blackhole()
    await check_gemini_api()
    await check_anthropic_api()
    check_data_dirs()
    check_port()

    # Summary
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed_critical = [(n, t) for n, ok, t in results if not ok and t == "critical"]
    failed_optional = [(n, t) for n, ok, t in results if not ok and t == "optional"]

    print(f"\n{BOLD}{'='*50}")
    print(f"  Results: {passed}/{total} passed")
    if failed_critical:
        print(f"  {RED}CRITICAL FAILURES: {len(failed_critical)}{RESET}")
        for name, _ in failed_critical:
            print(f"    - {name}")
    if failed_optional:
        print(f"  {YELLOW}Optional failures: {len(failed_optional)}{RESET}")
        for name, _ in failed_optional:
            print(f"    - {name}")
    if not failed_critical:
        print(f"  {GREEN}ALL CRITICAL CHECKS PASSED — ready for event{RESET}")
    print(f"{'='*50}\n")

    sys.exit(1 if failed_critical else 0)


if __name__ == "__main__":
    asyncio.run(main())
