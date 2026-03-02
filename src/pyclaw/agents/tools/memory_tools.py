"""Memory tools — search and retrieve from the memory store."""

from __future__ import annotations

from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult


class MemorySearchTool(BaseTool):
    """Semantically search memory files for prior context."""

    def __init__(self, *, memory_store: Any = None) -> None:
        self._store = memory_store

    @property
    def name(self) -> str:
        return "memory_search"

    @property
    def description(self) -> str:
        return (
            "Search your memory store for relevant prior context, decisions, "
            "preferences, and facts. Call this before answering questions about "
            "prior work, dates, people, or preferences."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language search query.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 10).",
                },
            },
            "required": ["query"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        if not self._store:
            return ToolResult.text(
                '{"disabled": true, "message": "Memory store is not configured."}',
            )

        query = arguments.get("query", "")
        if not query:
            return ToolResult.text("Error: query is required.", is_error=True)

        limit = arguments.get("limit", 10)

        try:
            results = self._store.search(query, limit=limit)
        except Exception as e:
            return ToolResult.text(f"Memory search error: {e}", is_error=True)

        if not results:
            return ToolResult.text("No matching memories found.")

        lines: list[str] = []
        for entry in results:
            d = entry.to_dict() if hasattr(entry, "to_dict") else {"content": str(entry)}
            lines.append(f"[id={d.get('id', '?')}] {d.get('content', '')[:200]}")
        return ToolResult.text("\n".join(lines))


class MemoryGetTool(BaseTool):
    """Read a specific memory entry by ID."""

    def __init__(self, *, memory_store: Any = None) -> None:
        self._store = memory_store

    @property
    def name(self) -> str:
        return "memory_get"

    @property
    def description(self) -> str:
        return "Read a specific snippet from memory by its ID, typically after memory_search."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "The memory entry ID to retrieve.",
                },
            },
            "required": ["id"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        if not self._store:
            return ToolResult.text("Memory store is not configured.", is_error=True)

        memory_id = arguments.get("id")
        if memory_id is None:
            return ToolResult.text("Error: id is required.", is_error=True)

        try:
            entry = self._store.get(int(memory_id))
        except Exception as e:
            return ToolResult.text(f"Memory get error: {e}", is_error=True)

        if not entry:
            return ToolResult.text(f"Memory entry {memory_id} not found.", is_error=True)

        d = entry.to_dict() if hasattr(entry, "to_dict") else {"content": str(entry)}
        import json

        return ToolResult.text(json.dumps(d, ensure_ascii=False, indent=2))
