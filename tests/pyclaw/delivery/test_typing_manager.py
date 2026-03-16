"""Tests for typing indicator manager."""

from __future__ import annotations

import asyncio
import time

import pytest

from pyclaw.channels.typing_manager import (
    TypingCircuitBreaker,
    TypingConfig,
    TypingManager,
)


class TestTypingCircuitBreaker:
    def test_initially_closed(self) -> None:
        cb = TypingCircuitBreaker()
        assert cb.is_open is False

    def test_opens_after_threshold(self) -> None:
        cb = TypingCircuitBreaker(threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is False
        cb.record_failure()
        assert cb.is_open is True

    def test_success_resets(self) -> None:
        cb = TypingCircuitBreaker(threshold=2)
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        assert cb.is_open is False

    def test_auto_reset_after_timeout(self) -> None:
        cb = TypingCircuitBreaker(threshold=1, reset_s=0.01)
        cb.record_failure()
        assert cb.is_open is True
        time.sleep(0.02)
        assert cb.is_open is False


class TestTypingManager:
    @pytest.fixture
    def manager(self) -> TypingManager:
        return TypingManager(TypingConfig(keepalive_interval_s=0.05, max_duration_s=1.0))

    @pytest.mark.asyncio
    async def test_start_and_stop(self, manager: TypingManager) -> None:
        calls = []

        async def cb() -> None:
            calls.append(time.time())

        session = await manager.start_typing("telegram", "chat1", cb)
        assert manager.active_count == 1
        assert len(calls) >= 1  # Initial trigger

        await asyncio.sleep(0.1)
        await manager.stop_typing("telegram", "chat1")
        assert manager.active_count == 0

    @pytest.mark.asyncio
    async def test_duplicate_start(self, manager: TypingManager) -> None:
        async def cb() -> None:
            pass

        s1 = await manager.start_typing("t", "c1", cb)
        s2 = await manager.start_typing("t", "c1", cb)
        assert s1 is s2
        await manager.stop_typing("t", "c1")

    @pytest.mark.asyncio
    async def test_mark_run_complete_stops(self, manager: TypingManager) -> None:
        async def cb() -> None:
            pass

        await manager.start_typing("t", "c1", cb)
        manager.mark_run_complete("t", "c1")
        await manager.mark_dispatch_idle("t", "c1")
        await asyncio.sleep(0.1)
        assert manager.active_count == 0

    @pytest.mark.asyncio
    async def test_force_cleanup(self, manager: TypingManager) -> None:
        async def cb() -> None:
            pass

        await manager.start_typing("t", "c1", cb)
        await manager.force_cleanup("t", "c1")
        assert manager.active_count == 0

    @pytest.mark.asyncio
    async def test_stop_all(self, manager: TypingManager) -> None:
        async def cb() -> None:
            pass

        await manager.start_typing("t", "c1", cb)
        await manager.start_typing("t", "c2", cb)
        await manager.stop_all()
        assert manager.active_count == 0

    @pytest.mark.asyncio
    async def test_ttl_safety_net(self) -> None:
        manager = TypingManager(TypingConfig(keepalive_interval_s=0.02, max_duration_s=0.05))

        async def cb() -> None:
            pass

        await manager.start_typing("t", "c1", cb)
        await asyncio.sleep(0.15)
        assert manager.active_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_on_failure(self, manager: TypingManager) -> None:
        call_count = 0

        async def failing_cb() -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("API error")

        await manager.start_typing("t", "c1", failing_cb)
        await asyncio.sleep(0.2)
        await manager.stop_typing("t", "c1")
        # Should have stopped calling after circuit breaker opened
        assert call_count <= 5
