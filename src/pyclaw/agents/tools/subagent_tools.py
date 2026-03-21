"""Subagent management tools — list, spawn, steer, kill sessions."""

from __future__ import annotations

from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult


class AgentsListTool(BaseTool):
    """List available agents and their configurations."""

    def __init__(self, *, agents_dir: Any = None) -> None:
        self._agents_dir = agents_dir

    @property
    def name(self) -> str:
        return "agents_list"

    @property
    def description(self) -> str:
        return "List available agents and their current status."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        from pathlib import Path

        from pyclaw.config.paths import resolve_agents_dir

        agents_dir = Path(self._agents_dir) if self._agents_dir else resolve_agents_dir()
        if not agents_dir.is_dir():
            return ToolResult.text("No agents directory found.")

        agents: list[str] = []
        for d in sorted(agents_dir.iterdir()):
            if d.is_dir():
                sessions_dir = d / "sessions"
                session_count = len(list(sessions_dir.glob("*.jsonl"))) if sessions_dir.is_dir() else 0
                agents.append(f"  {d.name}: {session_count} session(s)")

        if not agents:
            return ToolResult.text("No agents found.")
        return ToolResult.text(f"Agents ({len(agents)}):\n" + "\n".join(agents))


class SessionsSpawnTool(BaseTool):
    """Spawn a new subagent session."""

    def __init__(self, *, subagent_manager: Any = None) -> None:
        self._manager = subagent_manager

    @property
    def name(self) -> str:
        return "sessions_spawn"

    @property
    def description(self) -> str:
        return (
            "Spawn a new subagent session to perform a task. The subagent runs "
            "independently and returns its result. Use for delegating subtasks."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The task description for the subagent.",
                },
                "model": {
                    "type": "string",
                    "description": "Model to use for the subagent (optional, defaults to current).",
                },
            },
            "required": ["prompt"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        prompt = arguments.get("prompt", "")
        if not prompt:
            return ToolResult.text("Error: prompt is required.", is_error=True)

        if not self._manager:
            return ToolResult.text("Error: subagent manager not available.", is_error=True)

        from pyclaw.agents.subagents.types import SubagentConfig

        config = SubagentConfig(
            prompt=prompt,
            model=arguments.get("model", ""),
            system_prompt=None,
        )

        try:
            result = await self._manager.spawn(config)
            return ToolResult.text(
                f"Subagent completed ({result.state.value}):\n{result.output or result.error or '(no output)'}"
            )
        except Exception as e:
            return ToolResult.text(f"Subagent error: {e}", is_error=True)


class SubagentsTool(BaseTool):
    """Manage running subagents — list, steer, kill."""

    def __init__(self, *, subagent_manager: Any = None) -> None:
        self._manager = subagent_manager

    @property
    def name(self) -> str:
        return "subagents"

    @property
    def description(self) -> str:
        return (
            "Manage subagents. Actions: 'list' to see active subagents, "
            "'steer' to send instructions to a running subagent, "
            "'kill' to abort a subagent."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: 'list', 'steer', or 'kill'.",
                },
                "session_id": {
                    "type": "string",
                    "description": "Session ID of the subagent (required for steer/kill).",
                },
                "instruction": {
                    "type": "string",
                    "description": "Steering instruction (required for steer action).",
                },
            },
            "required": ["action"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        action = arguments.get("action", "")
        if not self._manager:
            return ToolResult.text("Error: subagent manager not available.", is_error=True)

        if action == "list":
            active = self._manager.list_active()
            if not active:
                return ToolResult.text("No active subagents.")
            lines = []
            for sa in active:
                lines.append(f"  {sa['session_id'][:8]}... ({sa['state']}) depth={sa['depth']} agent={sa['agent_id']}")
            return ToolResult.text(f"Active subagents ({len(active)}):\n" + "\n".join(lines))

        session_id = arguments.get("session_id", "")
        if not session_id:
            return ToolResult.text("Error: session_id required for steer/kill.", is_error=True)

        if action == "kill":
            ok = await self._manager.kill(session_id)
            return ToolResult.text("Killed." if ok else "Subagent not found.")

        if action == "steer":
            instruction = arguments.get("instruction", "")
            if not instruction:
                return ToolResult.text("Error: instruction required for steer.", is_error=True)
            ok = await self._manager.steer(session_id, instruction)
            return ToolResult.text("Steered." if ok else "Subagent not found or not running.")

        return ToolResult.text(f"Unknown action: {action}", is_error=True)


class SessionStatusTool(BaseTool):
    """Show current session usage/time/model status."""

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "session_status"

    @property
    def description(self) -> str:
        return (
            "Display the current session's status including model, token usage, "
            "context window utilization, and elapsed time."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        # This is a session-context-aware tool; in practice it reads from
        # the running agent's state. Returns a status card.
        return ToolResult.text(
            "Session Status:\n"
            "  Model: (resolved at runtime)\n"
            "  Tokens used: (tracked at runtime)\n"
            "  Context remaining: (tracked at runtime)\n"
            "  Duration: (tracked at runtime)\n"
            "\n(Full status requires runtime agent context)"
        )
