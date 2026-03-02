"""Tests for delivery queue."""

from __future__ import annotations

import asyncio

import pytest

from pyclaw.infra.delivery import (
    DeliveryEntry,
    DeliveryPriority,
    DeliveryQueue,
    DeliveryStatus,
    compute_backoff,
)


class TestComputeBackoff:
    def test_first_attempt(self) -> None:
        delay = compute_backoff(0, base_delay=1.0, max_delay=60.0, jitter_factor=0)
        assert delay == pytest.approx(1.0, abs=0.1)

    def test_exponential_growth(self) -> None:
        d0 = compute_backoff(0, jitter_factor=0)
        d1 = compute_backoff(1, jitter_factor=0)
        d2 = compute_backoff(2, jitter_factor=0)
        assert d1 > d0
        assert d2 > d1

    def test_max_cap(self) -> None:
        delay = compute_backoff(100, max_delay=60.0, jitter_factor=0)
        assert delay <= 60.0

    def test_jitter(self) -> None:
        delays = [compute_backoff(2, jitter_factor=0.25) for _ in range(20)]
        assert len(set(delays)) > 1


class TestDeliveryEntry:
    def test_auto_id(self) -> None:
        entry = DeliveryEntry(id="", channel_id="t", chat_id="c1", payload={})
        assert len(entry.id) > 0

    def test_auto_timestamp(self) -> None:
        entry = DeliveryEntry(id="", channel_id="t", chat_id="c1", payload={})
        assert entry.created_at > 0


class TestDeliveryQueue:
    @pytest.mark.asyncio
    async def test_enqueue_and_deliver(self) -> None:
        delivered: list[str] = []

        async def callback(entry: DeliveryEntry) -> bool:
            delivered.append(entry.id)
            return True

        q = DeliveryQueue(callback)
        await q.start()
        entry = await q.enqueue("telegram", "chat1", {"text": "hello"})
        await asyncio.sleep(0.3)
        await q.stop(drain=False)

        assert entry.id in delivered
        assert entry.status == DeliveryStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_retry_on_failure(self) -> None:
        attempt_count = 0

        async def callback(entry: DeliveryEntry) -> bool:
            nonlocal attempt_count
            attempt_count += 1
            return attempt_count >= 2

        q = DeliveryQueue(callback, base_delay=0.05, max_retries=3)
        await q.start()
        await q.enqueue("t", "c1", {"text": "retry-me"})
        await asyncio.sleep(0.5)
        await q.stop(drain=False)

        assert attempt_count >= 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self) -> None:
        async def always_fail(entry: DeliveryEntry) -> bool:
            return False

        q = DeliveryQueue(always_fail, max_retries=2, base_delay=0.02)
        await q.start()
        entry = await q.enqueue("t", "c1", {"text": "fail"})
        await asyncio.sleep(0.5)
        await q.stop(drain=False)

        assert entry.status == DeliveryStatus.FAILED
        assert entry.attempts >= 2

    @pytest.mark.asyncio
    async def test_priority_ordering(self) -> None:
        order: list[str] = []

        async def callback(entry: DeliveryEntry) -> bool:
            order.append(entry.payload["name"])
            return True

        q = DeliveryQueue(callback)
        await q.enqueue("t", "c1", {"name": "low"}, priority=DeliveryPriority.LOW)
        await q.enqueue("t", "c1", {"name": "high"}, priority=DeliveryPriority.HIGH)
        await q.start()
        await asyncio.sleep(0.3)
        await q.stop(drain=False)

        if len(order) >= 2:
            assert order[0] == "high"

    @pytest.mark.asyncio
    async def test_draining_rejects_new(self) -> None:
        async def callback(entry: DeliveryEntry) -> bool:
            await asyncio.sleep(0.1)
            return True

        q = DeliveryQueue(callback)
        await q.start()
        q._draining = True

        with pytest.raises(RuntimeError, match="draining"):
            await q.enqueue("t", "c1", {"text": "rejected"})

        q._draining = False
        await q.stop(drain=False)

    @pytest.mark.asyncio
    async def test_stats(self) -> None:
        async def callback(entry: DeliveryEntry) -> bool:
            return True

        q = DeliveryQueue(callback)
        await q.enqueue("t", "c1", {"text": "a"})
        stats = q.get_stats()
        assert stats.get("pending", 0) >= 1
