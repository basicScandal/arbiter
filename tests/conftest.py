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
from src.resilience.metrics import default_metrics
from src.resilience.rate_limiter import GeminiRateLimiter
from tests.helpers.event_collector import EventCollector


# ---------------------------------------------------------------------------
# Singleton reset (autouse)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset all module-level singletons before and after each test.

    Clears state in-place on the original singleton objects so that ALL
    references stay valid -- both module-attribute reads and import-time
    name bindings (e.g. ``from src.resilience.health import default_health``
    in pipeline.py). We also ensure the module attribute points to the
    canonical object in case a test replaced it.

    Covers:
    - EventBus (default_bus) -- subscribers and pending events
    - ServiceHealth (default_health) -- health/failure state
    - GeminiRateLimiter (_instance) -- semaphore state
    """
    _do_reset()
    yield
    _do_reset()


# Keep references to the original singletons captured at import time.
# These are the same objects that other modules bind when they do
# ``from src.resilience.health import default_health`` at module level.
_original_bus = event_bus_module.default_bus
_original_health = health_module.default_health


def _do_reset() -> None:
    """Clear singleton state in-place and restore module attributes."""
    # Clear EventBus state in-place
    _original_bus._subscribers.clear()
    _original_bus._global_subscribers.clear()
    _original_bus._pending_count = 0
    _original_bus._drain_event.set()
    # Ensure the module attribute points to the canonical object
    event_bus_module.default_bus = _original_bus

    # Clear Metrics state in-place
    default_metrics._counters.clear()
    default_metrics._timers.clear()

    # Clear ServiceHealth state in-place
    _original_health._healthy.clear()
    _original_health._last_failure.clear()
    _original_health._failure_count.clear()
    # Ensure the module attribute points to the canonical object
    health_module.default_health = _original_health

    # GeminiRateLimiter uses class-level singleton, no import-time binding issue
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
def vcr_config(request) -> dict:
    """Configure VCR for HTTP cassette recording/playback.

    Filters sensitive headers, stores cassettes in tests/cassettes/, and
    defaults to playback-only mode unless --record-mode is passed via CLI.
    """
    config: dict = {
        "filter_headers": [
            "authorization",
            "x-api-key",
            "x-goog-api-key",
            "anthropic-api-key",
        ],
        "cassette_library_dir": "tests/cassettes",
        "decode_compressed_response": True,
    }
    # Only hardcode "none" when the CLI flag isn't overriding it.
    # pytest-recording's --record-mode flag needs to win when present.
    if not request.config.getoption("--record-mode", default=None):
        config["record_mode"] = "none"
    return config
