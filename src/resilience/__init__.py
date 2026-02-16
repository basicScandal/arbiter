"""Resilience primitives: retry decorators and service health tracking.

Provides shared tenacity retry configs for Gemini API calls and a
ServiceHealth tracker for per-component healthy/unhealthy state with
timed exponential recovery windows.
"""

from src.resilience.health import ServiceHealth, default_health
from src.resilience.retry import GEMINI_RETRY, GEMINI_RETRY_BACKGROUND

__all__ = [
    "GEMINI_RETRY",
    "GEMINI_RETRY_BACKGROUND",
    "ServiceHealth",
    "default_health",
]
