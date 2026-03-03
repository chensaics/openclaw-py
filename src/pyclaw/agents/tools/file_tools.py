"""File operation tools — read, write, edit."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult

_MAX_READ_BYTES = 512 * 1024  # 512 KiB soft limit


def _resolve_path(raw: str, workspace_root: str | None) -> Path:
    """Resolve a path relative to the workspace root (if set)."""
    p = Path(raw).expanduser()
    if not p.is_absolute() and workspace_root:
        p = Path(workspace_root) / p
    return p.resolve()


def _check_path_safety(path: Path, workspace_root: str | None) -> str | None:
    """Return an error string if the path is outside the workspace."""
    if workspace_root:
        root = Path(workspace_root).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            return f"Path {path} is outside workspace root {root}"
    return None


class ReadTool(BaseTool):
    """Read file contents with optional line range."""

    def __init__(self, *, workspace_root: str | None = None) -> None:
        self._workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return (
            "Read the contents of a file. Returns the text content with line numbers. "
            "Optionally specify start_line and end_line to read a range."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read."},
                "start_line": {
                    "type": "integer",
                    "description": "1-based start line (inclusive). Omit to start from beginning.",
                },
                "end_line": {
                    "type": "integer",
                    "description": "1-based end line (inclusive). Omit to read to end.",
                },
            },
            "required": ["path"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        raw_path = arguments.get("path", "")
        if not raw_path:
            return ToolResult.text("Error: path is required.", is_error=True)

        path = _resolve_path(raw_path, self._workspace_root)
        if err := _check_path_safety(path, self._workspace_root):
            return ToolResult.text(err, is_error=True)

        if not path.exists():
            return ToolResult.text(f"File not found: {path}", is_error=True)
        if not path.is_file():
            return ToolResult.text(f"Not a file: {path}", is_error=True)

        try:
            size = path.stat().st_size
            if size > _MAX_READ_BYTES:
                return ToolResult.text(
                    f"File too large ({size} bytes, limit {_MAX_READ_BYTES}). "
                    "Use start_line/end_line to read a section.",
                    is_error=True,
                )

            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return ToolResult.text(f"Error reading file: {e}", is_error=True)

        lines = text.splitlines(keepends=True)
        start = arguments.get("start_line")
        end = arguments.get("end_line")

        if start is not None or end is not None:
            s = (start or 1) - 1
            end_idx = end or len(lines)
            lines = lines[s:end_idx]
            offset = s
        else:
            offset = 0

        numbered = "".join(f"{i + offset + 1:>6}|{line}" for i, line in enumerate(lines))
        return ToolResult.text(numbered or "(empty file)")


class WriteTool(BaseTool):
    """Create or overwrite a file."""

    def __init__(self, *, workspace_root: str | None = None) -> None:
        self._workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "write"

    @property
    def description(self) -> str:
        return "Create or overwrite a file with the given content."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write."},
                "content": {"type": "string", "description": "Content to write."},
            },
            "required": ["path", "content"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        raw_path = arguments.get("path", "")
        content = arguments.get("content", "")
        if not raw_path:
            return ToolResult.text("Error: path is required.", is_error=True)

        path = _resolve_path(raw_path, self._workspace_root)
        if err := _check_path_safety(path, self._workspace_root):
            return ToolResult.text(err, is_error=True)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except Exception as e:
            return ToolResult.text(f"Error writing file: {e}", is_error=True)

        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        return ToolResult.text(f"Wrote {len(content)} bytes ({line_count} lines) to {path}")


class EditTool(BaseTool):
    """Search-and-replace edit within a file."""

    def __init__(self, *, workspace_root: str | None = None) -> None:
        self._workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "edit"

    @property
    def description(self) -> str:
        return (
            "Edit a file by replacing an exact occurrence of old_string with new_string. "
            "The old_string must match exactly (including whitespace and indentation). "
            "Set replace_all=true to replace all occurrences."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to edit."},
                "old_string": {"type": "string", "description": "Exact text to find."},
                "new_string": {"type": "string", "description": "Replacement text."},
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences (default false).",
                },
            },
            "required": ["path", "old_string", "new_string"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        raw_path = arguments.get("path", "")
        old_string = arguments.get("old_string", "")
        new_string = arguments.get("new_string", "")
        replace_all = arguments.get("replace_all", False)

        if not raw_path:
            return ToolResult.text("Error: path is required.", is_error=True)
        if not old_string:
            return ToolResult.text("Error: old_string is required.", is_error=True)
        if old_string == new_string:
            return ToolResult.text("Error: old_string and new_string are identical.", is_error=True)

        path = _resolve_path(raw_path, self._workspace_root)
        if err := _check_path_safety(path, self._workspace_root):
            return ToolResult.text(err, is_error=True)

        if not path.exists():
            return ToolResult.text(f"File not found: {path}", is_error=True)

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            return ToolResult.text(f"Error reading file: {e}", is_error=True)

        count = content.count(old_string)
        if count == 0:
            return ToolResult.text(
                "Error: old_string not found in file. Make sure it matches exactly.",
                is_error=True,
            )
        if count > 1 and not replace_all:
            return ToolResult.text(
                f"Error: old_string found {count} times. "
                "Provide more context to make it unique, or set replace_all=true.",
                is_error=True,
            )

        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        try:
            path.write_text(new_content, encoding="utf-8")
        except Exception as e:
            return ToolResult.text(f"Error writing file: {e}", is_error=True)

        replaced = count if replace_all else 1
        return ToolResult.text(f"Replaced {replaced} occurrence(s) in {path}")
