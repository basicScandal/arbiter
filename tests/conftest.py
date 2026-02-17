"""Shared test fixtures for the arbiter test suite.

Provides:
- Autouse singleton reset to prevent state leakage between tests
- Fresh EventBus and EventCollector fixtures for async event testing
- VCR configuration for HTTP cassette recording/playback
"""

from __future__ import annotations

import pytest

from src.capture.event_bus import EventBus
import src.capture.event_bus as event_bus_module
import src.resilience.health as health_module
from src.resilience.health import ServiceHealth
from src.resilience.rate_limiter import GeminiRateLimiter
from tests.helpers.event_collector import EventCollector


# ---------------------------------------------------------------------------
# Singleton reset (autouse)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset all module-level singletons before and after each test.

    Prevents state leakage between tests by replacing module-level singleton
    instances with fresh objects. Covers:
    - EventBus (default_bus) -- subscribers and pending events
    - ServiceHealth (default_health) -- health/failure state
    - GeminiRateLimiter (_instance) -- semaphore state
    """
    event_bus_module.default_bus = EventBus()
    health_module.default_health = ServiceHealth()
    GeminiRateLimiter._instance = None
    yield
    event_bus_module.default_bus = EventBus()
    health_module.default_health = ServiceHealth()
    GeminiRateLimiter._instance = None


# ---------------------------------------------------------------------------
# EventBus and EventCollector fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def event_bus() -> EventBus:
    """Provide a fresh EventBus instance isolated from the module singleton."""
    return EventBus()


@pytest.fixture
def event_collector(event_bus: EventBus) -> EventCollector:
    """Provide an EventCollector bound to the test's event_bus fixture."""
    return EventCollector(event_bus)


# ---------------------------------------------------------------------------
# VCR / cassette configuration
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def vcr_config() -> dict:
    """Configure VCR for HTTP cassette recording/playback.

    Filters sensitive headers, disables recording by default (playback only),
    and stores cassettes in tests/cassettes/.
    """
    return {
        "filter_headers": [
            "authorization",
            "x-api-key",
            "x-goog-api-key",
            "anthropic-api-key",
        ],
        "record_mode": "none",
        "cassette_library_dir": "tests/cassettes",
        "decode_compressed_response": True,
    }
