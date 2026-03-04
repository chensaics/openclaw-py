"""Memory-core extension — registers memory hooks and tools as a non-channel extension.

Ported from ``extensions/memory-core/`` in the TypeScript codebase.

Provides:
- Memory auto-recall hook (inject relevant memories into context)
- Memory auto-capture hook (save notable exchanges)
- Memory management tools (search, add, delete, list)
- Extension lifecycle (on_load, on_unload)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MemoryToolConfig:
    """Configuration for memory tools."""

    enabled: bool = True
    auto_recall: bool = True
    auto_capture: bool = False
    max_recall_results: int = 5
    min_relevance_score: float = 0.5
    capture_min_turns: int = 3


@dataclass
class MemoryEntry:
    """A single memory entry."""

    id: str
    content: str
    created_at: float = 0.0
    updated_at: float = 0.0
    tags: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
    source: str = ""  # "auto" | "manual" | "hook"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.updated_at == 0.0:
            self.updated_at = self.created_at


class MemoryCoreExtension:
    """Memory-core extension providing hooks and tools for memory management."""

    name = "memory-core"
    version = "1.0.0"

    def __init__(self, config: MemoryToolConfig | None = None) -> None:
        self._config = config or MemoryToolConfig()
        self._memories: list[MemoryEntry] = []
        self._loaded = False

    async def on_load(self) -> None:
        """Called when the extension is loaded."""
        self._loaded = True
        logger.info("Memory-core extension loaded (auto_recall=%s)", self._config.auto_recall)

    async def on_unload(self) -> None:
        """Called when the extension is unloaded."""
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def get_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions for memory management."""
        if not self._config.enabled:
            return []

        return [
            {
                "name": "memory_search",
                "description": "Search memories for relevant context",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "memory_add",
                "description": "Save a new memory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Memory content"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["content"],
                },
            },
            {
                "name": "memory_delete",
                "description": "Delete a memory by ID",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Memory ID"},
                    },
                    "required": ["id"],
                },
            },
            {
                "name": "memory_list",
                "description": "List recent memories",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Max results"},
                    },
                },
            },
        ]

    def add_memory(
        self,
        content: str,
        *,
        tags: list[str] | None = None,
        source: str = "manual",
    ) -> MemoryEntry:
        """Add a new memory entry."""
        entry = MemoryEntry(
            id=f"mem_{len(self._memories)}_{int(time.time())}",
            content=content,
            tags=tags or [],
            source=source,
        )
        self._memories.append(entry)
        return entry

    def search_memories(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        """Search memories by keyword matching.

        For production use, integrate with a vector backend
        (e.g. ``memory/lancedb_backend.py``).
        """
        query_lower = query.lower()
        scored: list[tuple[float, MemoryEntry]] = []

        for entry in self._memories:
            content_lower = entry.content.lower()
            if query_lower in content_lower:
                # Simple relevance: position-weighted
                pos = content_lower.index(query_lower)
                score = 1.0 - (pos / max(len(content_lower), 1))
                scored.append((score, entry))
            else:
                # Check tags
                for tag in entry.tags:
                    if query_lower in tag.lower():
                        scored.append((0.5, entry))
                        break

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        for i, entry in enumerate(self._memories):
            if entry.id == memory_id:
                self._memories.pop(i)
                return True
        return False

    def list_memories(self, *, limit: int = 20) -> list[MemoryEntry]:
        """List recent memories."""
        return sorted(self._memories, key=lambda e: e.created_at, reverse=True)[:limit]

    def auto_recall(self, context: str) -> list[MemoryEntry]:
        """Auto-recall relevant memories for context injection.

        Searches with individual significant words from the context
        to improve recall across varied phrasing.
        """
        if not self._config.auto_recall:
            return []

        # Try full context first
        results = self.search_memories(context[:200], limit=self._config.max_recall_results)
        if results:
            return results

        # Fall back to individual word search
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "about",
            "me",
            "my",
            "i",
            "you",
            "it",
            "and",
            "or",
            "but",
            "tell",
            "what",
            "how",
            "do",
            "does",
            "can",
        }
        words = [w for w in context.lower().split() if w not in stop_words and len(w) > 2]

        seen_ids: set[str] = set()
        for word in words[:5]:
            for entry in self.search_memories(word, limit=self._config.max_recall_results):
                if entry.id not in seen_ids:
                    seen_ids.add(entry.id)
                    results.append(entry)

        return results[: self._config.max_recall_results]

    def auto_capture(self, exchange: str, *, turn_count: int = 0) -> MemoryEntry | None:
        """Auto-capture a notable exchange as a memory."""
        if not self._config.auto_capture:
            return None
        if turn_count < self._config.capture_min_turns:
            return None
        return self.add_memory(exchange[:500], source="auto", tags=["auto-captured"])

    @property
    def memory_count(self) -> int:
        return len(self._memories)
