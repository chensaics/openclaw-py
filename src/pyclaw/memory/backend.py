"""Pluggable memory backend protocol — abstract interface for memory storage.

Defines ``MemoryBackend`` so memory storage can be swapped between
SQLite (default), LanceDB, or any other vector/hybrid store.
The auto-recall/auto-capture hooks inject memories into agent context
and extract them from conversations automatically.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MemoryRecord:
    """A memory entry returned from a backend."""

    id: str
    content: str
    source: str = ""
    tags: list[str] = field(default_factory=list)
    score: float = 0.0
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemorySearchOptions:
    """Options for searching memories."""

    limit: int = 10
    min_score: float = 0.0
    tags: list[str] | None = None
    source: str | None = None


class MemoryBackend(ABC):
    """Abstract memory backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier (e.g. 'sqlite', 'lancedb')."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the backend (create tables, connect, etc.)."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the backend and release resources."""
        ...

    @abstractmethod
    async def add(
        self,
        content: str,
        *,
        source: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> MemoryRecord:
        """Add a memory entry."""
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        embedding: list[float] | None = None,
        options: MemorySearchOptions | None = None,
    ) -> list[MemoryRecord]:
        """Search memories by query text and/or embedding vector."""
        ...

    @abstractmethod
    async def delete(self, record_id: str) -> bool:
        """Delete a memory by ID."""
        ...

    @abstractmethod
    async def count(self) -> int:
        """Return total number of memories."""
        ...

    async def list_recent(self, *, limit: int = 20) -> list[MemoryRecord]:
        """List recent memories. Default implementation searches with empty query."""
        return await self.search("", options=MemorySearchOptions(limit=limit))


# ---------------------------------------------------------------------------
# Auto-recall / auto-capture
# ---------------------------------------------------------------------------


@dataclass
class AutoRecallConfig:
    """Configuration for automatic memory recall."""

    enabled: bool = True
    max_results: int = 5
    min_score: float = 0.1
    inject_as_system: bool = True


@dataclass
class AutoCaptureConfig:
    """Configuration for automatic memory capture."""

    enabled: bool = True
    extract_facts: bool = True
    extract_preferences: bool = True
    source_label: str = "auto-capture"


class MemoryManager:
    """Manages a pluggable memory backend with auto-recall/capture hooks."""

    def __init__(
        self,
        backend: MemoryBackend,
        *,
        recall_config: AutoRecallConfig | None = None,
        capture_config: AutoCaptureConfig | None = None,
    ) -> None:
        self.backend = backend
        self.recall_config = recall_config or AutoRecallConfig()
        self.capture_config = capture_config or AutoCaptureConfig()

    async def initialize(self) -> None:
        await self.backend.initialize()

    async def close(self) -> None:
        await self.backend.close()

    async def auto_recall(
        self,
        query: str,
        *,
        embedding: list[float] | None = None,
    ) -> list[MemoryRecord]:
        """Recall relevant memories for a user message."""
        if not self.recall_config.enabled:
            return []

        options = MemorySearchOptions(
            limit=self.recall_config.max_results,
            min_score=self.recall_config.min_score,
        )
        results = await self.backend.search(query, embedding=embedding, options=options)
        return results

    def format_recall_context(self, memories: list[MemoryRecord]) -> str:
        """Format recalled memories as system context."""
        if not memories:
            return ""

        lines = ["<recalled_memories>"]
        for m in memories:
            tag_str = f" [{', '.join(m.tags)}]" if m.tags else ""
            lines.append(f"- {m.content}{tag_str}")
        lines.append("</recalled_memories>")
        return "\n".join(lines)

    async def auto_capture(
        self,
        user_message: str,
        assistant_response: str,
        *,
        extracted_facts: list[str] | None = None,
    ) -> list[MemoryRecord]:
        """Capture memories from a conversation turn."""
        if not self.capture_config.enabled:
            return []

        if not extracted_facts:
            return []

        captured: list[MemoryRecord] = []
        for fact in extracted_facts:
            record = await self.backend.add(
                content=fact,
                source=self.capture_config.source_label,
                tags=["auto-captured"],
            )
            captured.append(record)
            logger.debug("Auto-captured memory: %s", fact[:80])

        return captured


# ---------------------------------------------------------------------------
# Backend registry
# ---------------------------------------------------------------------------

_backend_factories: dict[str, type[MemoryBackend]] = {}


def register_memory_backend(name: str, factory: type[MemoryBackend]) -> None:
    """Register a memory backend factory."""
    _backend_factories[name] = factory


def get_memory_backend_factory(name: str) -> type[MemoryBackend] | None:
    """Get a registered memory backend factory by name."""
    return _backend_factories.get(name)


def list_memory_backends() -> list[str]:
    """List registered backend names."""
    return sorted(_backend_factories.keys())
