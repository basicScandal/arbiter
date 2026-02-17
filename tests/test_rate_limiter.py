"""Test suite for the Gemini API rate limiter.

Tests the GeminiRateLimiter singleton, semaphore-based concurrency limiting,
acquire/release lifecycle, logging behavior, and edge cases including
serialization, cancellation, and exception safety.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import patch

import pytest

from src.resilience.rate_limiter import GeminiRateLimiter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singleton() -> None:
    """Reset the GeminiRateLimiter singleton before each test."""
    GeminiRateLimiter._instance = None


@pytest.fixture
def limiter() -> GeminiRateLimiter:
    """Create a fresh rate limiter with default max_concurrent=2."""
    return GeminiRateLimiter()


@pytest.fixture
def serial_limiter() -> GeminiRateLimiter:
    """Create a rate limiter that serializes all calls (max_concurrent=1)."""
    return GeminiRateLimiter(max_concurrent=1)


# ---------------------------------------------------------------------------
# Singleton pattern tests
# ---------------------------------------------------------------------------


class TestSingletonPattern:
    """Tests for the GeminiRateLimiter singleton pattern."""

    def test_default_returns_instance(self) -> None:
        """default() should create and return a GeminiRateLimiter instance."""
        instance = GeminiRateLimiter.default()
        assert isinstance(instance, GeminiRateLimiter)

    def test_default_returns_same_instance(self) -> None:
        """Repeated calls to default() should return the same instance."""
        first = GeminiRateLimiter.default()
        second = GeminiRateLimiter.default()
        assert first is second

    def test_default_creates_new_instance_after_reset(self) -> None:
        """After resetting _instance, default() should create a new instance."""
        first = GeminiRateLimiter.default()
        GeminiRateLimiter._instance = None
        second = GeminiRateLimiter.default()
        assert first is not second

    def test_singleton_is_independent_of_constructor(self) -> None:
        """Directly constructed instances should not affect the singleton."""
        direct = GeminiRateLimiter(max_concurrent=5)
        singleton = GeminiRateLimiter.default()
        assert direct is not singleton


# ---------------------------------------------------------------------------
# Semaphore concurrency limiting tests
# ---------------------------------------------------------------------------


class TestConcurrencyLimiting:
    """Tests for semaphore-based concurrency control."""

    @pytest.mark.asyncio
    async def test_two_tasks_run_concurrently(self, limiter: GeminiRateLimiter) -> None:
        """With max_concurrent=2, two tasks should run at the same time."""
        running = 0
        max_running = 0

        async def task() -> None:
            nonlocal running, max_running
            async with limiter.acquire("test"):
                running += 1
                max_running = max(max_running, running)
                await asyncio.sleep(0.05)
                running -= 1

        await asyncio.gather(task(), task())
        assert max_running == 2

    @pytest.mark.asyncio
    async def test_third_task_blocked_until_release(self, limiter: GeminiRateLimiter) -> None:
        """With max_concurrent=2, a third task must wait for one to finish."""
        gate1 = asyncio.Event()
        gate2 = asyncio.Event()
        entered = asyncio.Event()
        order: list[str] = []

        async def holder(name: str, gate: asyncio.Event) -> None:
            async with limiter.acquire(name):
                order.append(f"{name}_acquired")
                await gate.wait()
                order.append(f"{name}_released")

        async def waiter() -> None:
            async with limiter.acquire("waiter"):
                entered.set()
                order.append("waiter_acquired")

        t1 = asyncio.create_task(holder("h1", gate1))
        t2 = asyncio.create_task(holder("h2", gate2))
        await asyncio.sleep(0.01)  # Let holders acquire

        t3 = asyncio.create_task(waiter())
        await asyncio.sleep(0.01)  # Waiter should be blocked
        assert not entered.is_set(), "Third task should be blocked"

        gate1.set()  # Release one holder
        await asyncio.sleep(0.01)
        assert entered.is_set(), "Third task should proceed after one release"

        gate2.set()
        await asyncio.gather(t1, t2, t3)

    @pytest.mark.asyncio
    async def test_concurrency_timing(self, limiter: GeminiRateLimiter) -> None:
        """Three tasks of 0.1s each with max_concurrent=2 should take ~0.2s, not 0.1s or 0.3s."""

        async def work() -> None:
            async with limiter.acquire("timing"):
                await asyncio.sleep(0.1)

        loop = asyncio.get_event_loop()
        start = loop.time()
        await asyncio.gather(work(), work(), work())
        elapsed = loop.time() - start

        # Should be ~0.2s: two run concurrently, then the third
        assert elapsed >= 0.15, f"Too fast ({elapsed:.3f}s) - concurrency not limited"
        assert elapsed < 0.35, f"Too slow ({elapsed:.3f}s) - tasks may be serialized"

    @pytest.mark.asyncio
    async def test_max_concurrent_respected(self, limiter: GeminiRateLimiter) -> None:
        """Peak concurrency should never exceed max_concurrent."""
        running = 0
        peak = 0

        async def task() -> None:
            nonlocal running, peak
            async with limiter.acquire("peak"):
                running += 1
                peak = max(peak, running)
                await asyncio.sleep(0.02)
                running -= 1

        await asyncio.gather(*[task() for _ in range(6)])
        assert peak <= 2


# ---------------------------------------------------------------------------
# Acquire/release lifecycle tests
# ---------------------------------------------------------------------------


class TestAcquireRelease:
    """Tests for the acquire context manager lifecycle."""

    @pytest.mark.asyncio
    async def test_acquire_and_release(self, limiter: GeminiRateLimiter) -> None:
        """Context manager should acquire and cleanly release the semaphore."""
        async with limiter.acquire("lifecycle"):
            # Semaphore internal value should be reduced
            assert limiter._semaphore._value == 1  # 2 - 1 = 1

        # After exit, semaphore should be fully restored
        assert limiter._semaphore._value == 2

    @pytest.mark.asyncio
    async def test_exception_inside_context_releases_semaphore(
        self, limiter: GeminiRateLimiter
    ) -> None:
        """An exception inside acquire() should still release the semaphore."""
        with pytest.raises(ValueError, match="boom"):
            async with limiter.acquire("error"):
                raise ValueError("boom")

        # Semaphore should be fully released despite the exception
        assert limiter._semaphore._value == 2

    @pytest.mark.asyncio
    async def test_sequential_acquires(self, limiter: GeminiRateLimiter) -> None:
        """Multiple sequential acquire/release cycles should work correctly."""
        for i in range(5):
            async with limiter.acquire(f"seq-{i}"):
                assert limiter._semaphore._value == 1

        assert limiter._semaphore._value == 2

    @pytest.mark.asyncio
    async def test_yield_provides_none(self, limiter: GeminiRateLimiter) -> None:
        """The context manager should yield None."""
        async with limiter.acquire("yield-test") as value:
            assert value is None


# ---------------------------------------------------------------------------
# Logging tests
# ---------------------------------------------------------------------------


class TestLogging:
    """Tests for debug log messages during acquire/release."""

    @pytest.mark.asyncio
    async def test_log_messages_with_caller(
        self, limiter: GeminiRateLimiter, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Acquiring, acquired, and released log messages should include caller name."""
        with caplog.at_level(logging.DEBUG, logger="src.resilience.rate_limiter"):
            async with limiter.acquire("commentary"):
                pass

        messages = [r.message for r in caplog.records]
        assert any("commentary acquiring" in m for m in messages)
        assert any("commentary acquired" in m for m in messages)
        assert any("commentary released" in m for m in messages)

    @pytest.mark.asyncio
    async def test_log_messages_empty_caller(
        self, limiter: GeminiRateLimiter, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Empty caller string should default to 'unknown' in log messages."""
        with caplog.at_level(logging.DEBUG, logger="src.resilience.rate_limiter"):
            async with limiter.acquire():
                pass

        messages = [r.message for r in caplog.records]
        assert any("unknown acquiring" in m for m in messages)
        assert any("unknown acquired" in m for m in messages)
        assert any("unknown released" in m for m in messages)

    @pytest.mark.asyncio
    async def test_log_messages_explicit_empty_string(
        self, limiter: GeminiRateLimiter, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Explicitly passing empty string should also use 'unknown'."""
        with caplog.at_level(logging.DEBUG, logger="src.resilience.rate_limiter"):
            async with limiter.acquire(caller=""):
                pass

        messages = [r.message for r in caplog.records]
        assert all("unknown" in m for m in messages if "Rate limiter" in m)

    @pytest.mark.asyncio
    async def test_log_level_is_debug(
        self, limiter: GeminiRateLimiter, caplog: pytest.LogCaptureFixture
    ) -> None:
        """All rate limiter log messages should be at DEBUG level."""
        with caplog.at_level(logging.DEBUG, logger="src.resilience.rate_limiter"):
            async with limiter.acquire("level-check"):
                pass

        for record in caplog.records:
            assert record.levelno == logging.DEBUG


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and unusual usage patterns."""

    @pytest.mark.asyncio
    async def test_max_concurrent_one_serializes(
        self, serial_limiter: GeminiRateLimiter
    ) -> None:
        """With max_concurrent=1, tasks should run one at a time."""
        running = 0
        peak = 0

        async def task() -> None:
            nonlocal running, peak
            async with serial_limiter.acquire("serial"):
                running += 1
                peak = max(peak, running)
                await asyncio.sleep(0.02)
                running -= 1

        await asyncio.gather(*[task() for _ in range(4)])
        assert peak == 1, "max_concurrent=1 should serialize all tasks"

    @pytest.mark.asyncio
    async def test_nested_acquire_with_capacity(self, limiter: GeminiRateLimiter) -> None:
        """Nested acquire with enough capacity (max=2) should succeed."""
        async with limiter.acquire("outer"):
            async with limiter.acquire("inner"):
                assert limiter._semaphore._value == 0

        assert limiter._semaphore._value == 2

    @pytest.mark.asyncio
    async def test_nested_acquire_deadlocks_at_max_one(
        self, serial_limiter: GeminiRateLimiter
    ) -> None:
        """Nested acquire with max_concurrent=1 should deadlock (timeout)."""
        with pytest.raises(asyncio.TimeoutError):
            async with serial_limiter.acquire("outer"):
                await asyncio.wait_for(
                    serial_limiter.acquire("inner").__aenter__(),
                    timeout=0.2,
                )

    @pytest.mark.asyncio
    async def test_cancellation_of_waiting_task(self, serial_limiter: GeminiRateLimiter) -> None:
        """Cancelling a task waiting on the semaphore should not corrupt state."""
        holder_ready = asyncio.Event()
        release_holder = asyncio.Event()

        async def holder() -> None:
            async with serial_limiter.acquire("holder"):
                holder_ready.set()
                await release_holder.wait()

        async def waiter() -> None:
            async with serial_limiter.acquire("waiter"):
                pass  # Should never reach here

        holder_task = asyncio.create_task(holder())
        await holder_ready.wait()

        waiter_task = asyncio.create_task(waiter())
        await asyncio.sleep(0.01)  # Let waiter start waiting
        waiter_task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await waiter_task

        # Release the holder
        release_holder.set()
        await holder_task

        # Semaphore should still work after cancellation
        assert serial_limiter._semaphore._value == 1
        async with serial_limiter.acquire("after-cancel"):
            assert serial_limiter._semaphore._value == 0

    @pytest.mark.asyncio
    async def test_custom_max_concurrent(self) -> None:
        """Custom max_concurrent values should be respected."""
        limiter = GeminiRateLimiter(max_concurrent=5)
        running = 0
        peak = 0

        async def task() -> None:
            nonlocal running, peak
            async with limiter.acquire("custom"):
                running += 1
                peak = max(peak, running)
                await asyncio.sleep(0.05)
                running -= 1

        await asyncio.gather(*[task() for _ in range(10)])
        assert peak == 5

    @pytest.mark.asyncio
    async def test_exception_in_one_task_does_not_affect_others(
        self, limiter: GeminiRateLimiter
    ) -> None:
        """An exception in one task should not prevent other tasks from acquiring."""
        results: list[str] = []

        async def failing_task() -> None:
            async with limiter.acquire("fail"):
                raise RuntimeError("task failed")

        async def healthy_task() -> None:
            async with limiter.acquire("healthy"):
                results.append("ok")

        with pytest.raises(RuntimeError):
            await failing_task()

        await healthy_task()
        assert results == ["ok"]
        assert limiter._semaphore._value == 2
