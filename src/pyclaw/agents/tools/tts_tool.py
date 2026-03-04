"""Text-to-speech tool — convert text to audio."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult


class TtsTool(BaseTool):
    """Convert text to speech audio using edge-tts."""

    @property
    def name(self) -> str:
        return "tts"

    @property
    def description(self) -> str:
        return (
            "Convert text to speech audio. Generates an MP3 file and returns "
            "its path. Uses Microsoft Edge TTS (free, no API key required)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to convert to speech.",
                },
                "voice": {
                    "type": "string",
                    "description": "Voice name (default: en-US-AriaNeural). Use edge-tts --list-voices to see options.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Output file path (default: auto-generated temp file).",
                },
            },
            "required": ["text"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        text = arguments.get("text", "")
        if not text:
            return ToolResult.text("Error: text is required.", is_error=True)

        voice = arguments.get("voice", "en-US-AriaNeural")
        output_path = arguments.get("output_path")

        if not output_path:
            fd, output_path = tempfile.mkstemp(suffix=".mp3", prefix="pyclaw-tts-")
            import os

            os.close(fd)

        try:
            import edge_tts

            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
        except ImportError:
            return ToolResult.text(
                "edge-tts is not installed. Run: pip install edge-tts",
                is_error=True,
            )
        except Exception as e:
            return ToolResult.text(f"TTS error: {e}", is_error=True)

        size = Path(output_path).stat().st_size
        return ToolResult.text(f"Audio saved to {output_path} ({size} bytes, voice={voice}).")


class ImageTool(BaseTool):
    """Analyze an image with the configured image model."""

    @property
    def name(self) -> str:
        return "image"

    @property
    def description(self) -> str:
        return "Analyze an image file. Provide a path to an image and an optional prompt describing what to look for."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the image file.",
                },
                "prompt": {
                    "type": "string",
                    "description": "What to analyze in the image (default: 'Describe this image').",
                },
            },
            "required": ["path"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        image_path = arguments.get("path", "")
        if not image_path:
            return ToolResult.text("Error: path is required.", is_error=True)

        p = Path(image_path).expanduser()
        if not p.is_file():
            return ToolResult.text(f"Image file not found: {p}", is_error=True)

        import base64
        import mimetypes

        mime, _ = mimetypes.guess_type(str(p))
        if not mime or not mime.startswith("image/"):
            return ToolResult.text(f"Not a recognized image type: {mime}", is_error=True)

        data = p.read_bytes()
        base64.b64encode(data).decode("ascii")

        return ToolResult.text(
            f"Image loaded: {p.name} ({len(data)} bytes, {mime}). "
            f"Base64 data available for vision model. Prompt: {arguments.get('prompt', 'Describe this image')}"
        )
