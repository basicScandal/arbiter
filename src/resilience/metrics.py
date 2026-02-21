"""In-process metrics for observability.

Module-level singleton (default_metrics) holds counters and optional
histogram-like buckets. Exposed as JSON at /api/metrics and optionally
as Prometheus text format for scraping.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict


class Metrics:
    """Thread-safe counters and simple timers for key pipeline events."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._timers: dict[str, list[float]] = defaultdict(list)
        self._max_timer_samples = 1000

    def inc(self, name: str, value: int = 1) -> None:
        """Increment a counter."""
        with self._lock:
            self._counters[name] += value

    def observe_seconds(self, name: str, seconds: float) -> None:
        """Record a duration for a named operation (keeps last N samples)."""
        with self._lock:
            buf = self._timers[name]
            buf.append(seconds)
            if len(buf) > self._max_timer_samples:
                buf.pop(0)

    def get_counters(self) -> dict[str, int]:
        """Return a snapshot of all counters."""
        with self._lock:
            return dict(self._counters)

    def get_timers(self) -> dict[str, dict[str, float]]:
        """Return timer stats (count, sum, avg) per name."""
        with self._lock:
            out: dict[str, dict[str, float]] = {}
            for name, samples in self._timers.items():
                if not samples:
                    continue
                n = len(samples)
                s = sum(samples)
                out[name] = {"count": n, "sum_sec": s, "avg_sec": s / n}
            return out

    def snapshot(self) -> dict:
        """Full snapshot for JSON response."""
        return {
            "counters": self.get_counters(),
            "timers": self.get_timers(),
        }

    def prometheus_text(self) -> str:
        """Export counters and timer sums in Prometheus exposition format."""
        lines = ["# HELP arbiter_* Arbiter pipeline metrics", "# TYPE arbiter_counter counter"]
        with self._lock:
            for name, value in sorted(self._counters.items()):
                safe = name.replace(".", "_").replace("-", "_")
                lines.append(f"arbiter_counter_{safe} {value}")
            lines.append("# TYPE arbiter_timer_seconds_total counter")
            for name, samples in sorted(self._timers.items()):
                if not samples:
                    continue
                safe = name.replace(".", "_").replace("-", "_")
                total = sum(samples)
                lines.append(f"arbiter_timer_seconds_total_{safe} {total:.6f}")
        return "\n".join(lines) + "\n"


default_metrics = Metrics()
"""Module-level singleton for app-wide metrics."""
