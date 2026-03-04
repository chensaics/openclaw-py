"""Send file tool — deliver files to the user via the current channel."""

from __future__ import annotations

import mimetypes
import os
from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult


def _detect_file_type(mime: str) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("text/"):
        return "text"
    return "file"


class SendFileTool(BaseTool):
    """Send a file to the user through the active channel."""

    @property
    def name(self) -> str:
        return "send_file"

    @property
    def description(self) -> str:
        return (
            "Send a file to the user. Automatically detects MIME type and sends "
            "as image, audio, video, or generic file attachment."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file to send.",
                },
            },
            "required": ["file_path"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        file_path = arguments.get("file_path", "").strip()
        if not file_path:
            return ToolResult.text("Error: file_path is required.", is_error=True)

        if not os.path.exists(file_path):
            return ToolResult.text(f"Error: File not found: {file_path}", is_error=True)

        if not os.path.isfile(file_path):
            return ToolResult.text(f"Error: Not a file: {file_path}", is_error=True)

        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = "application/octet-stream"

        file_type = _detect_file_type(mime_type)
        abs_path = os.path.abspath(file_path)
        size_bytes = os.path.getsize(abs_path)
        size_display = (
            f"{size_bytes / 1024:.1f} KB" if size_bytes < 1024 * 1024 else f"{size_bytes / (1024 * 1024):.1f} MB"
        )

        if file_type == "text":
            try:
                with open(abs_path, encoding="utf-8") as f:
                    content = f.read()
                if len(content) > 50000:
                    content = content[:50000] + "\n... (truncated)"
                return ToolResult.text(f"[File: {os.path.basename(abs_path)} ({size_display})]\n\n{content}")
            except UnicodeDecodeError:
                pass

        return ToolResult.text(
            f"File ready to send: {os.path.basename(abs_path)}\n"
            f"  Type: {file_type} ({mime_type})\n"
            f"  Size: {size_display}\n"
            f"  Path: {abs_path}"
        )
