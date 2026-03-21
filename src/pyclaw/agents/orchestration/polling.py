"""Polling tools for async spawned subagents."""

from __future__ import annotations

import asyncio
from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult


class SubagentPollTool(BaseTool):
    """Poll async spawned subagent status."""

    def __init__(self, *, subagent_manager: Any = None) -> None:
        self._manager = subagent_manager

    @property
    def name(self) -> str:
        return "subagent_poll"

    @property
    def description(self) -> str:
        return (
            "Check the status of an asynchronously spawned subagent. "
            "Returns state, output preview, and whether it's still running."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID of the subagent to poll.",
                },
            },
            "required": ["session_id"],
        }

    async def execute(
        self,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Check the status of an async spawned subagent."""
        if not self._manager:
            return ToolResult.text("Error: subagent manager not available.", is_error=True)

        session_id = arguments.get("session_id", "")
        if not session_id:
            return ToolResult.text("Error: session_id is required.", is_error=True)

        # Find in active or completed
        entry = self._manager._active.get(session_id)

        # Check recently completed
        if not entry:
            for completed in self._manager._completed[-50:]:
                if completed.get("session_id") == session_id:
                    return ToolResult.json(
                        {
                            "status": "COMPLETED",
                            "session_id": session_id,
                            "output_preview": completed.get("output_preview", "")[:200],
                            "is_running": False,
                        }
                    )

        # Still active
        if entry:
            return ToolResult.json(
                {
                    "status": entry.state.value,
                    "session_id": session_id,
                    "output_preview": "",
                    "is_running": True,
                }
            )

        return ToolResult.text(f"Subagent {session_id} not found in active or recent history.")


class SubagentJoinTool(BaseTool):
    """Wait for async spawned subagent to complete."""

    def __init__(self, *, subagent_manager: Any = None) -> None:
        self._manager = subagent_manager

    @property
    def name(self) -> str:
        return "subagent_join"

    @property
    def description(self) -> str:
        return (
            "Wait for an asynchronously spawned subagent to complete and return its result. "
            "Blocks until to the subagent finishes, fails, or is killed."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID of the subagent to join.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds to wait before timing out.",
                },
            },
            "required": ["session_id"],
        }

    async def execute(
        self,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Wait for async spawned subagent to complete and return its result."""
        if not self._manager:
            return ToolResult.text("Error: subagent manager not available.", is_error=True)

        session_id = arguments.get("session_id", "")
        timeout = arguments.get("timeout", 300)

        if not session_id:
            return ToolResult.text("Error: session_id is required.", is_error=True)

        # Find active entry
        entry = self._manager._active.get(session_id)

        if not entry or not entry.future:
            # Check recent completions
            for completed in self._manager._completed[-20:]:
                if completed.get("session_id") == session_id:
                    return ToolResult.json(
                        {
                            "status": "COMPLETED",
                            "output": completed.get("output", ""),
                            "session_id": session_id,
                        }
                    )

            return ToolResult.text(f"Subagent {session_id} not found or already completed.")

        # Wait for the future
        try:
            result = await asyncio.wait_for(entry.future, timeout=timeout)

            return ToolResult.json(
                {
                    "status": result.state.value,
                    "output": result.output or "",
                    "error": result.error or "",
                    "meta": result.meta.model_dump() if result.meta else {},
                    "session_id": session_id,
                }
            )

        except asyncio.TimeoutError:
            # Try to kill the stalled subagent
            await self._manager.kill(session_id)

            return ToolResult.json(
                {
                    "status": "TIMEOUT",
                    "error": f"Subagent timed out after {timeout}s",
                    "session_id": session_id,
                }
            )
