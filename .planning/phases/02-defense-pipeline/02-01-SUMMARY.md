---
phase: 02-defense-pipeline
plan: 01
subsystem: defense
tags: [pydantic, regex, ocr, pytesseract, opencv, injection-detection]

# Dependency graph
requires:
  - phase: 01-capture-layer
    provides: "CaptureEvent base class, FrameData with jpeg_data, event bus pattern"
provides:
  - "InjectionPattern, DetectionResult, InjectionAttempt, SanitizedOutput models"
  - "InjectionDetected, RoastGenerated, ObservationVerified event types"
  - "OCRScanner for extracting text from JPEG key frames"
  - "InjectionDetector with 10 regex patterns across 5 categories and confidence scoring"
affects: [02-02, 02-03, 03-commentary, 04-scoring]

# Tech tracking
tech-stack:
  added: [pytesseract~=0.3.13, tesseract-ocr (system)]
  patterns: [confidence-scoring injection detection, graceful-degradation OCR, defense-as-middleware models]

key-files:
  created:
    - src/defense/__init__.py
    - src/defense/models.py
    - src/defense/ocr_scanner.py
    - src/defense/injection_detector.py
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "Empty bytes guard in OCR scanner to prevent OpenCV assertion error on empty input"

patterns-established:
  - "Defense models extend CaptureEvent for event bus integration"
  - "Confidence scoring: high (2+ high-severity matches), medium (1 high or 2+ medium), low (otherwise)"
  - "OCR graceful degradation: warn on missing Tesseract, return empty strings, never crash"

# Metrics
duration: 2min
completed: 2026-02-15
---

# Phase 2 Plan 1: Defense Models, OCR Scanner, and Injection Detector Summary

**Pydantic defense models with typed injection contracts, OCR text extraction via pytesseract with adaptive threshold preprocessing, and 10-pattern regex injection detector with confidence scoring across 5 attack categories**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-16T06:54:45Z
- **Completed:** 2026-02-16T06:57:19Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Defense data models define typed contracts for the entire pipeline: InjectionPattern, DetectionResult, InjectionAttempt, SanitizedOutput
- Three defense event types (InjectionDetected, RoastGenerated, ObservationVerified) extend CaptureEvent for event bus integration
- OCR scanner extracts text from JPEG key frames with grayscale + adaptive threshold preprocessing, handling missing Tesseract gracefully
- Injection detector scans text across 5 categories (instruction_override, scoring, role_manipulation, extraction, context_escape) with 10 patterns
- Confidence scoring requires multiple high-severity matches for "high" confidence, reducing false positives at a security hackathon

## Task Commits

Each task was committed atomically:

1. **Task 1: Defense data models and event types** - `474c01c` (feat)
2. **Task 2: OCR scanner and injection detector** - `c4b0160` (feat)

## Files Created/Modified
- `src/defense/__init__.py` - Package init with docstring
- `src/defense/models.py` - InjectionPattern, DetectionResult, InjectionAttempt, SanitizedOutput, InjectionDetected, RoastGenerated, ObservationVerified
- `src/defense/ocr_scanner.py` - OCRScanner with Tesseract availability check, JPEG decode, grayscale + adaptive threshold preprocessing, timeout protection
- `src/defense/injection_detector.py` - INJECTION_PATTERNS (10 patterns, 5 categories), InjectionDetector with confidence scoring and source-specific scan methods
- `pyproject.toml` - Added pytesseract~=0.3.13 dependency
- `uv.lock` - Lock file updated with pytesseract + packaging

## Decisions Made
- Added empty bytes guard in OCR scanner to prevent OpenCV assertion error on empty input (auto-fixed during verification)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added empty bytes guard in OCR scanner**
- **Found during:** Task 2 (OCR scanner edge case testing)
- **Issue:** `cv2.imdecode` throws an assertion error when given an empty numpy array from empty bytes input
- **Fix:** Added `if not jpeg_data: return ""` guard before numpy/OpenCV processing
- **Files modified:** src/defense/ocr_scanner.py
- **Verification:** Empty bytes now returns empty string without error
- **Committed in:** c4b0160 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Essential for robustness. No scope creep.

## Issues Encountered
None

## User Setup Required
Tesseract OCR system binary must be installed for OCR scanning to function:
- macOS: `brew install tesseract`
- Linux: `apt install tesseract-ocr`
- Note: The OCR scanner degrades gracefully if Tesseract is not installed (logs warning, returns empty strings)

## Next Phase Readiness
- Defense models ready for use by sanitizer (Plan 02-02) and pipeline wiring (Plan 02-03)
- OCR scanner ready for key frame text extraction via asyncio.to_thread
- Injection detector ready for visual, verbal, and observation text scanning
- All 10 patterns tested; confidence scoring verified with multi-pattern injection text

## Self-Check: PASSED

All 4 created files verified on disk. Both task commits (474c01c, c4b0160) verified in git history.

---
*Phase: 02-defense-pipeline*
*Completed: 2026-02-15*
