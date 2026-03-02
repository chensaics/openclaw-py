"""Agent tools for canvas interaction — read/write/navigate canvas files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pyclaw.canvas.handler import resolve_file_within_root


def tool_canvas_read() -> dict[str, Any]:
    """Tool definition for reading a canvas file."""
    return {
        "name": "canvas_read",
        "description": "Read a file from the user's canvas directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path within the canvas root"},
            },
            "required": ["path"],
        },
    }


def tool_canvas_write() -> dict[str, Any]:
    """Tool definition for writing a canvas file."""
    return {
        "name": "canvas_write",
        "description": "Write or create a file in the user's canvas directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path within the canvas root"},
                "content": {"type": "string", "description": "File content to write"},
            },
            "required": ["path", "content"],
        },
    }


def tool_canvas_list() -> dict[str, Any]:
    """Tool definition for listing canvas directory contents."""
    return {
        "name": "canvas_list",
        "description": "List files and directories in the canvas root.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Subdirectory to list (default: root)",
                    "default": "",
                },
            },
        },
    }


def tool_canvas_snapshot() -> dict[str, Any]:
    """Tool definition for taking a canvas snapshot."""
    return {
        "name": "canvas_snapshot",
        "description": "Take a snapshot of the current canvas state (creates a timestamped copy).",
        "parameters": {"type": "object", "properties": {}},
    }


def _get_canvas_root() -> Path:
    root = Path.home() / ".pyclaw" / "state" / "canvas"
    root.mkdir(parents=True, exist_ok=True)
    return root


async def handle_canvas_read(params: dict[str, Any], context: Any = None) -> str:
    """Read a file from canvas."""
    path = params.get("path", "")
    if not path:
        return "Error: path is required"

    root = _get_canvas_root()
    file = resolve_file_within_root(root, path)
    if not file:
        return f"File not found: {path}"

    try:
        return file.read_text("utf-8")
    except Exception as exc:
        return f"Error reading {path}: {exc}"


async def handle_canvas_write(params: dict[str, Any], context: Any = None) -> str:
    """Write a file to canvas."""
    path = params.get("path", "")
    content = params.get("content", "")
    if not path:
        return "Error: path is required"

    root = _get_canvas_root()
    target = (root / path.lstrip("/")).resolve()
    if not str(target).startswith(str(root.resolve())):
        return "Error: path traversal not allowed"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, "utf-8")
    return f"Written {len(content)} chars to {path}"


async def handle_canvas_list(params: dict[str, Any], context: Any = None) -> str:
    """List canvas directory contents."""
    path = params.get("path", "")
    root = _get_canvas_root()

    target = (root / path.lstrip("/")).resolve() if path else root
    if not str(target).startswith(str(root.resolve())):
        return "Error: path traversal not allowed"

    if not target.is_dir():
        return f"Not a directory: {path}"

    entries: list[str] = []
    for item in sorted(target.iterdir()):
        if item.name.startswith("."):
            continue
        kind = "dir" if item.is_dir() else "file"
        size = item.stat().st_size if item.is_file() else 0
        entries.append(f"  {kind:4s} {item.name}" + (f" ({size} bytes)" if size else ""))

    if not entries:
        return f"Empty directory: {path or '/'}"
    return f"Canvas {path or '/'}:\n" + "\n".join(entries)


async def handle_canvas_snapshot(params: dict[str, Any], context: Any = None) -> str:
    """Take a timestamped snapshot of the canvas directory."""
    import shutil
    import time

    root = _get_canvas_root()
    snapshot_dir = root.parent / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%d-%H%M%S")
    dest = snapshot_dir / f"canvas-{ts}"
    shutil.copytree(root, dest, dirs_exist_ok=True)
    return f"Snapshot created: {dest.name}"
