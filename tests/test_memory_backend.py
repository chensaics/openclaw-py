"""Tests for pluggable memory backend and auto-recall/capture."""

from __future__ import annotations

import pytest

from pyclaw.memory.backend import (
    AutoCaptureConfig,
    AutoRecallConfig,
    MemoryBackend,
    MemoryManager,
    MemoryRecord,
    MemorySearchOptions,
    get_memory_backend_factory,
    list_memory_backends,
    register_memory_backend,
)
from typing import Any
import time


class InMemoryBackend(MemoryBackend):
    """Simple in-memory backend for testing."""

    def __init__(self) -> None:
        self._records: dict[str, MemoryRecord] = {}
        self._counter = 0

    @property
    def name(self) -> str:
        return "in-memory"

    async def initialize(self) -> None:
        pass

    async def close(self) -> None:
        self._records.clear()

    async def add(
        self,
        content: str,
        *,
        source: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> MemoryRecord:
        self._counter += 1
        record = MemoryRecord(
            id=str(self._counter),
            content=content,
            source=source,
            tags=tags or [],
            score=1.0,
            created_at=time.time(),
            metadata=metadata or {},
        )
        self._records[record.id] = record
        return record

    async def search(
        self,
        query: str,
        *,
        embedding: list[float] | None = None,
        options: MemorySearchOptions | None = None,
    ) -> list[MemoryRecord]:
        opts = options or MemorySearchOptions()
        results = []
        for r in self._records.values():
            if not query or query.lower() in r.content.lower():
                if r.score >= opts.min_score:
                    results.append(r)
        return results[: opts.limit]

    async def delete(self, record_id: str) -> bool:
        return self._records.pop(record_id, None) is not None

    async def count(self) -> int:
        return len(self._records)


class TestMemoryBackendProtocol:
    @pytest.mark.asyncio
    async def test_add_and_search(self) -> None:
        backend = InMemoryBackend()
        await backend.initialize()

        record = await backend.add("Python is great", source="test", tags=["lang"])
        assert record.id == "1"
        assert record.content == "Python is great"

        results = await backend.search("python")
        assert len(results) == 1
        assert results[0].content == "Python is great"

        await backend.close()

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        backend = InMemoryBackend()
        await backend.initialize()

        record = await backend.add("temp entry")
        assert await backend.count() == 1

        deleted = await backend.delete(record.id)
        assert deleted is True
        assert await backend.count() == 0

        deleted = await backend.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_search_options(self) -> None:
        backend = InMemoryBackend()
        await backend.initialize()

        for i in range(5):
            await backend.add(f"item {i}")

        results = await backend.search("item", options=MemorySearchOptions(limit=3))
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_list_recent_default(self) -> None:
        backend = InMemoryBackend()
        await backend.initialize()
        await backend.add("a")
        await backend.add("b")
        results = await backend.list_recent(limit=10)
        assert len(results) == 2


class TestMemoryManager:
    @pytest.fixture
    def backend(self) -> InMemoryBackend:
        return InMemoryBackend()

    @pytest.mark.asyncio
    async def test_auto_recall_enabled(self, backend: InMemoryBackend) -> None:
        manager = MemoryManager(
            backend,
            recall_config=AutoRecallConfig(enabled=True, max_results=3),
        )
        await manager.initialize()
        await backend.add("User likes coffee")

        results = await manager.auto_recall("coffee")
        assert len(results) == 1
        assert "coffee" in results[0].content

    @pytest.mark.asyncio
    async def test_auto_recall_disabled(self, backend: InMemoryBackend) -> None:
        manager = MemoryManager(
            backend,
            recall_config=AutoRecallConfig(enabled=False),
        )
        await manager.initialize()
        await backend.add("User likes coffee")

        results = await manager.auto_recall("coffee")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_format_recall_context(self, backend: InMemoryBackend) -> None:
        manager = MemoryManager(backend)
        records = [
            MemoryRecord(id="1", content="Likes coffee", tags=["preference"]),
            MemoryRecord(id="2", content="Lives in SF"),
        ]
        text = manager.format_recall_context(records)
        assert "<recalled_memories>" in text
        assert "Likes coffee [preference]" in text
        assert "Lives in SF" in text

    @pytest.mark.asyncio
    async def test_format_empty_recall(self, backend: InMemoryBackend) -> None:
        manager = MemoryManager(backend)
        assert manager.format_recall_context([]) == ""

    @pytest.mark.asyncio
    async def test_auto_capture(self, backend: InMemoryBackend) -> None:
        manager = MemoryManager(
            backend,
            capture_config=AutoCaptureConfig(enabled=True, source_label="test"),
        )
        await manager.initialize()

        captured = await manager.auto_capture(
            "I like tea",
            "Noted!",
            extracted_facts=["User likes tea"],
        )
        assert len(captured) == 1
        assert captured[0].content == "User likes tea"
        assert captured[0].source == "test"
        assert await backend.count() == 1

    @pytest.mark.asyncio
    async def test_auto_capture_disabled(self, backend: InMemoryBackend) -> None:
        manager = MemoryManager(
            backend,
            capture_config=AutoCaptureConfig(enabled=False),
        )
        await manager.initialize()

        captured = await manager.auto_capture(
            "I like tea", "Noted!", extracted_facts=["User likes tea"]
        )
        assert len(captured) == 0

    @pytest.mark.asyncio
    async def test_auto_capture_no_facts(self, backend: InMemoryBackend) -> None:
        manager = MemoryManager(backend)
        await manager.initialize()
        captured = await manager.auto_capture("hi", "hello")
        assert len(captured) == 0


class TestBackendRegistry:
    def test_register_and_lookup(self) -> None:
        register_memory_backend("test-mem", InMemoryBackend)
        factory = get_memory_backend_factory("test-mem")
        assert factory is InMemoryBackend

    def test_list_backends(self) -> None:
        register_memory_backend("test-list", InMemoryBackend)
        backends = list_memory_backends()
        assert "test-list" in backends

    def test_unknown_backend(self) -> None:
        assert get_memory_backend_factory("nonexistent-xyz") is None
