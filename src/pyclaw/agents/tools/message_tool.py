"""Message tool — cross-channel message sending."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult


class MessageTool(BaseTool):
    """Send messages and channel actions."""

    owner_only = True

    def __init__(
        self,
        *,
        send_fn: Callable[..., Coroutine[Any, Any, Any]] | None = None,
    ) -> None:
        self._send_fn = send_fn

    @property
    def name(self) -> str:
        return "message"

    @property
    def description(self) -> str:
        return (
            "Send a message to a specific channel and recipient. "
            "Use this for cross-channel messaging (e.g. sending a Telegram message "
            "from within a Discord session)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Target channel ID (e.g. 'telegram', 'discord', 'slack').",
                },
                "recipient": {
                    "type": "string",
                    "description": "Recipient identifier (chat ID, user ID, channel name).",
                },
                "text": {
                    "type": "string",
                    "description": "Message text to send.",
                },
            },
            "required": ["channel", "recipient", "text"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        channel = arguments.get("channel", "")
        recipient = arguments.get("recipient", "")
        text = arguments.get("text", "")

        if not channel or not recipient or not text:
            return ToolResult.text(
                "Error: channel, recipient, and text are all required.", is_error=True
            )

        if self._send_fn:
            try:
                await self._send_fn(channel=channel, recipient=recipient, text=text)
                return ToolResult.text(f"Message sent to {channel}:{recipient}.")
            except Exception as e:
                return ToolResult.text(f"Failed to send message: {e}", is_error=True)

        return ToolResult.text(
            "Message sending is not configured. No channel manager is connected.",
            is_error=True,
        )
