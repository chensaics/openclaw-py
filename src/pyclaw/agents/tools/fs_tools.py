"""File-system search tools — grep, find (glob), ls."""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.tools.file_tools import _check_path_safety, _resolve_path
from pyclaw.agents.types import ToolResult

_MAX_RESULTS = 500
_MAX_CONTEXT_LINES = 5


class GrepTool(BaseTool):
    """Search file contents by regex or literal pattern."""

    def __init__(self, *, workspace_root: str | None = None) -> None:
        self._workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return (
            "Search file contents using a regex pattern. Searches recursively from "
            "the given directory (defaults to workspace root). Returns matching lines "
            "with file paths and line numbers. Supports context lines (-A/-B/-C) and "
            "case-insensitive search. Use the 'include' parameter to filter by glob "
            "pattern (e.g. '*.py')."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for."},
                "path": {
                    "type": "string",
                    "description": "Directory or file to search in. Defaults to workspace root.",
                },
                "include": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g. '*.py', '*.ts').",
                },
                "case_insensitive": {
                    "type": "boolean",
                    "description": "Case-insensitive search (default false).",
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Number of context lines before and after each match (0-5).",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        pattern_str = arguments.get("pattern", "")
        if not pattern_str:
            return ToolResult.text("Error: pattern is required.", is_error=True)

        raw_path = arguments.get("path", self._workspace_root or ".")
        include = arguments.get("include")
        case_insensitive = arguments.get("case_insensitive", False)
        ctx = min(arguments.get("context_lines", 0), _MAX_CONTEXT_LINES)

        search_path = _resolve_path(raw_path, self._workspace_root)
        if err := _check_path_safety(search_path, self._workspace_root):
            return ToolResult.text(err, is_error=True)
        if not search_path.exists():
            return ToolResult.text(f"Path not found: {search_path}", is_error=True)

        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern_str, flags)
        except re.error as e:
            return ToolResult.text(f"Invalid regex: {e}", is_error=True)

        results: list[str] = []
        match_count = 0
        files_searched = 0

        def _should_include(name: str) -> bool:
            if not include:
                return True
            return fnmatch.fnmatch(name, include)

        def _search_file(fpath: Path) -> None:
            nonlocal match_count
            if match_count >= _MAX_RESULTS:
                return
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except (OSError, UnicodeDecodeError):
                return

            for i, line in enumerate(lines):
                if match_count >= _MAX_RESULTS:
                    return
                if regex.search(line):
                    match_count += 1
                    rel = fpath.relative_to(search_path) if search_path.is_dir() else fpath.name
                    start = max(0, i - ctx)
                    end = min(len(lines), i + ctx + 1)
                    if ctx > 0:
                        block = []
                        for j in range(start, end):
                            prefix = ":" if j == i else "-"
                            block.append(f"{rel}:{j + 1}{prefix}{lines[j]}")
                        results.append("\n".join(block))
                        results.append("--")
                    else:
                        results.append(f"{rel}:{i + 1}:{line}")

        if search_path.is_file():
            files_searched = 1
            _search_file(search_path)
        else:
            skip_dirs = {
                ".git",
                "node_modules",
                "__pycache__",
                ".venv",
                "venv",
                ".tox",
                "dist",
                "build",
            }
            for dirpath, dirnames, filenames in os.walk(search_path):
                dirnames[:] = [d for d in dirnames if d not in skip_dirs]
                for fname in filenames:
                    if not _should_include(fname):
                        continue
                    files_searched += 1
                    _search_file(Path(dirpath) / fname)
                    if match_count >= _MAX_RESULTS:
                        break
                if match_count >= _MAX_RESULTS:
                    break

        if match_count == 0:
            return ToolResult.text(f"No matches found ({files_searched} files searched).")

        header = f"Found {match_count} match(es) in {files_searched} files searched"
        if match_count >= _MAX_RESULTS:
            header += f" (truncated at {_MAX_RESULTS})"
        return ToolResult.text(header + "\n\n" + "\n".join(results))


class FindTool(BaseTool):
    """Find files by glob pattern."""

    def __init__(self, *, workspace_root: str | None = None) -> None:
        self._workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "find"

    @property
    def description(self) -> str:
        return (
            "Find files matching a glob pattern. Searches recursively from the given "
            "directory (defaults to workspace root). Returns matching file paths sorted "
            "by modification time (newest first). Use '**/' prefix for recursive matching."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match (e.g. '*.py', '**/*.test.ts', 'src/**/*.rs').",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in. Defaults to workspace root.",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        pattern = arguments.get("pattern", "")
        if not pattern:
            return ToolResult.text("Error: pattern is required.", is_error=True)

        raw_path = arguments.get("path", self._workspace_root or ".")
        search_path = _resolve_path(raw_path, self._workspace_root)
        if err := _check_path_safety(search_path, self._workspace_root):
            return ToolResult.text(err, is_error=True)
        if not search_path.exists():
            return ToolResult.text(f"Path not found: {search_path}", is_error=True)

        if not pattern.startswith("**/") and "/" not in pattern:
            pattern = "**/" + pattern

        try:
            matches: list[tuple[float, Path]] = []
            for p in search_path.glob(pattern):
                if p.is_file():
                    skip = {".git", "node_modules", "__pycache__", ".venv", "venv"}
                    if any(part in skip for part in p.parts):
                        continue
                    try:
                        mtime = p.stat().st_mtime
                    except OSError:
                        mtime = 0
                    matches.append((mtime, p))
                    if len(matches) >= _MAX_RESULTS:
                        break
        except Exception as e:
            return ToolResult.text(f"Error during glob: {e}", is_error=True)

        if not matches:
            return ToolResult.text(f"No files found matching '{pattern}'.")

        matches.sort(key=lambda x: x[0], reverse=True)
        lines = []
        for _, fpath in matches:
            try:
                rel = fpath.relative_to(search_path)
            except ValueError:
                rel = fpath
            lines.append(str(rel))

        header = f"Found {len(matches)} file(s)"
        if len(matches) >= _MAX_RESULTS:
            header += f" (truncated at {_MAX_RESULTS})"
        return ToolResult.text(header + "\n\n" + "\n".join(lines))


class LsTool(BaseTool):
    """List directory contents."""

    def __init__(self, *, workspace_root: str | None = None) -> None:
        self._workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "ls"

    @property
    def description(self) -> str:
        return (
            "List the contents of a directory. Shows files and subdirectories with "
            "sizes. By default lists the workspace root. Use 'recursive=true' for "
            "a tree view (limited depth)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to list. Defaults to workspace root.",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Recursively list subdirectories (max depth 3, default false).",
                },
            },
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        raw_path = arguments.get("path", self._workspace_root or ".")
        recursive = arguments.get("recursive", False)

        dir_path = _resolve_path(raw_path, self._workspace_root)
        if err := _check_path_safety(dir_path, self._workspace_root):
            return ToolResult.text(err, is_error=True)
        if not dir_path.exists():
            return ToolResult.text(f"Path not found: {dir_path}", is_error=True)
        if not dir_path.is_dir():
            return ToolResult.text(f"Not a directory: {dir_path}", is_error=True)

        lines: list[str] = []
        skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox"}
        max_depth = 3 if recursive else 1
        count = 0

        def _list_dir(d: Path, depth: int, prefix: str) -> None:
            nonlocal count
            if count >= _MAX_RESULTS:
                return
            try:
                entries = sorted(d.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
            except PermissionError:
                return

            for entry in entries:
                if count >= _MAX_RESULTS:
                    lines.append(f"{prefix}... (truncated)")
                    return
                if entry.name in skip_dirs:
                    continue

                count += 1
                if entry.is_dir():
                    lines.append(f"{prefix}{entry.name}/")
                    if recursive and depth < max_depth:
                        _list_dir(entry, depth + 1, prefix + "  ")
                else:
                    try:
                        size = entry.stat().st_size
                        size_str = _format_size(size)
                    except OSError:
                        size_str = "?"
                    lines.append(f"{prefix}{entry.name}  ({size_str})")

        _list_dir(dir_path, 1, "")

        if not lines:
            return ToolResult.text("(empty directory)")
        return ToolResult.text("\n".join(lines))


def _format_size(size: int) -> str:
    """Human-readable file size."""
    if size < 1024:
        return f"{size}B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f}MB"
    return f"{size / (1024 * 1024 * 1024):.1f}GB"
