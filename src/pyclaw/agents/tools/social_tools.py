"""Agent social tools — join/leave/status for agent social platforms."""

from __future__ import annotations

from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult


class SocialJoinTool(BaseTool):
    """Join an agent social platform (Moltbook, ClawdChat, etc.)."""

    def __init__(self, registry: Any = None) -> None:
        self._registry = registry

    @property
    def name(self) -> str:
        return "social_join"

    @property
    def description(self) -> str:
        return (
            "Join an agent social platform. Supported platforms: moltbook, clawdchat. "
            "The agent will register its profile and begin receiving messages."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "Platform to join: moltbook or clawdchat",
                    "enum": ["moltbook", "clawdchat"],
                },
                "display_name": {
                    "type": "string",
                    "description": "Agent display name on the platform",
                },
                "description": {
                    "type": "string",
                    "description": "Short description of the agent",
                },
            },
            "required": ["platform"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        platform_id = arguments.get("platform", "")
        display_name = arguments.get("display_name", "pyclaw-agent")
        description = arguments.get("description", "")

        if not self._registry:
            return ToolResult(
                tool_call_id=tool_call_id,
                output="Social platform registry not configured.",
                is_error=True,
            )

        from pyclaw.social.registry import AgentProfile

        platform = self._registry.get(platform_id)
        if not platform:
            available = [p["id"] for p in self._registry.list_platforms()]
            return ToolResult(
                tool_call_id=tool_call_id,
                output=f"Unknown platform '{platform_id}'. Available: {available}",
                is_error=True,
            )

        profile = AgentProfile(
            agent_id=f"pyclaw-{platform_id}",
            display_name=display_name,
            description=description,
            capabilities=["chat", "tools"],
        )

        success = await platform.join(profile)
        if success:
            return ToolResult(
                tool_call_id=tool_call_id,
                output=f"Joined {platform.display_name} as '{display_name}'.",
            )
        return ToolResult(
            tool_call_id=tool_call_id,
            output=f"Failed to join {platform.display_name}.",
            is_error=True,
        )


class SocialStatusTool(BaseTool):
    """Check agent social platform status."""

    def __init__(self, registry: Any = None) -> None:
        self._registry = registry

    @property
    def name(self) -> str:
        return "social_status"

    @property
    def description(self) -> str:
        return "Check the status of connected agent social platforms."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        if not self._registry:
            return ToolResult(
                tool_call_id=tool_call_id,
                output="Social platform registry not configured.",
                is_error=True,
            )

        platforms = self._registry.list_platforms()
        if not platforms:
            return ToolResult(
                tool_call_id=tool_call_id,
                output="No social platforms registered.",
            )

        lines = []
        for p in platforms:
            lines.append(f"- {p['name']} ({p['id']}): {p['status']}")

        return ToolResult(
            tool_call_id=tool_call_id,
            output="\n".join(lines),
        )
