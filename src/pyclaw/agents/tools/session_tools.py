"""Session management tools — list, send, spawn."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult


class SessionsListTool(BaseTool):
    """List available agent sessions."""

    def __init__(self, *, agents_dir: Path | None = None) -> None:
        self._agents_dir = agents_dir

    @property
    def name(self) -> str:
        return "sessions_list"

    @property
    def description(self) -> str:
        return (
            "List other sessions (including sub-agents) with optional filters. "
            "Use to check what sessions exist before sending messages or fetching history."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Filter by agent ID (default: all agents).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of sessions to return (default 20).",
                },
            },
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        agents_dir = self._agents_dir
        if not agents_dir or not agents_dir.is_dir():
            return ToolResult.text("No agents directory found.", is_error=True)

        agent_id = arguments.get("agent_id")
        limit = arguments.get("limit", 20)

        sessions: list[dict[str, Any]] = []
        dirs = [agents_dir / agent_id] if agent_id else sorted(agents_dir.iterdir())

        for agent_dir in dirs:
            if not agent_dir.is_dir():
                continue
            sessions_dir = agent_dir / "sessions"
            if not sessions_dir.is_dir():
                continue
            for session_file in sorted(sessions_dir.glob("*.jsonl"), reverse=True):
                sessions.append(
                    {
                        "agent": agent_dir.name,
                        "session": session_file.stem,
                        "size": session_file.stat().st_size,
                    }
                )
                if len(sessions) >= limit:
                    break
            if len(sessions) >= limit:
                break

        return ToolResult.text(json.dumps(sessions, indent=2))


class SessionsSendTool(BaseTool):
    """Send a message to another session/sub-agent."""

    owner_only = True

    @property
    def name(self) -> str:
        return "sessions_send"

    @property
    def description(self) -> str:
        return (
            "Send a message to another session or sub-agent. "
            "The message will be appended to the target session's transcript."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Target agent ID.",
                },
                "session_id": {
                    "type": "string",
                    "description": "Target session ID.",
                },
                "message": {
                    "type": "string",
                    "description": "Message text to send.",
                },
            },
            "required": ["agent_id", "session_id", "message"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        # Placeholder — requires gateway integration for cross-session messaging
        return ToolResult.text(
            "sessions_send is not yet connected to a live gateway. Message was not delivered."
        )
