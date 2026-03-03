"""Clipboard tool — read/write system clipboard from agent context."""

from __future__ import annotations

from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult


class ClipboardReadTool(BaseTool):
    """Read the system clipboard contents."""

    owner_only = True

    @property
    def name(self) -> str:
        return "clipboard_read"

    @property
    def description(self) -> str:
        return "Read the current contents of the system clipboard."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        from pyclaw.infra.misc_extras import clipboard_read

        content = clipboard_read()
        if content:
            return ToolResult.text(content)
        return ToolResult.text("Clipboard is empty or could not be read.")


class ClipboardWriteTool(BaseTool):
    """Write text to the system clipboard."""

    owner_only = True

    @property
    def name(self) -> str:
        return "clipboard_write"

    @property
    def description(self) -> str:
        return "Write text to the system clipboard."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to copy to the clipboard",
                },
            },
            "required": ["text"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        from pyclaw.infra.misc_extras import clipboard_write

        text = arguments.get("text", "")
        if not text:
            return ToolResult.text("No text provided.", is_error=True)

        success = clipboard_write(text)
        if success:
            return ToolResult.text(f"Copied {len(text)} characters to clipboard.")
        return ToolResult.text("Failed to write to clipboard.", is_error=True)
