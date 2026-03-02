"""Desktop screenshot tool — OS-level full-screen or window capture."""

from __future__ import annotations

import os
import platform
import subprocess
import tempfile
import time
from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult


class DesktopScreenshotTool(BaseTool):
    """Capture a screenshot of the entire desktop or a specific window."""

    @property
    def name(self) -> str:
        return "desktop_screenshot"

    @property
    def description(self) -> str:
        return (
            "Capture a screenshot of the entire desktop (all monitors) or a single window. "
            "Returns the path to the saved PNG file."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to save the screenshot (optional, auto-generated if empty).",
                },
                "capture_window": {
                    "type": "boolean",
                    "description": "If true on macOS, capture a specific window instead of full screen.",
                    "default": False,
                },
            },
            "required": [],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        path = (arguments.get("path") or "").strip()
        capture_window = arguments.get("capture_window", False)

        if not path:
            path = os.path.join(
                tempfile.gettempdir(), f"desktop_screenshot_{int(time.time())}.png",
            )
        if not path.lower().endswith(".png"):
            path += ".png"

        system = platform.system()

        if system == "Darwin" and capture_window:
            return await self._capture_macos_window(path)

        return await self._capture_mss(path)

    async def _capture_mss(self, path: str) -> ToolResult:
        try:
            import mss
        except ImportError:
            return ToolResult.text(
                "Error: mss package required. Install with: pip install mss",
                is_error=True,
            )
        try:
            with mss.mss() as sct:
                sct.shot(mon=0, output=path)
            if not os.path.isfile(path):
                return ToolResult.text("Screenshot failed: file not created", is_error=True)
            return ToolResult.text(f"Desktop screenshot saved to {path}")
        except Exception as exc:
            return ToolResult.text(f"Screenshot failed: {exc}", is_error=True)

    async def _capture_macos_window(self, path: str) -> ToolResult:
        cmd = ["screencapture", "-x", "-w", path]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, check=False,
            )
            if result.returncode != 0:
                stderr = (result.stderr or "").strip() or "Unknown error"
                return ToolResult.text(f"screencapture failed: {stderr}", is_error=True)
            if not os.path.isfile(path):
                return ToolResult.text("screencapture: file not created", is_error=True)
            return ToolResult.text(f"Window screenshot saved to {path}")
        except subprocess.TimeoutExpired:
            return ToolResult.text("screencapture timed out", is_error=True)
        except Exception as exc:
            return ToolResult.text(f"screencapture failed: {exc}", is_error=True)
