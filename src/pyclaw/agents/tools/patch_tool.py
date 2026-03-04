"""Apply-patch tool — multi-file unified diff application."""

from __future__ import annotations

import re
from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.tools.file_tools import _check_path_safety, _resolve_path
from pyclaw.agents.types import ToolResult


class ApplyPatchTool(BaseTool):
    """Apply a unified diff patch to one or more files."""

    def __init__(self, *, workspace_root: str | None = None) -> None:
        self._workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "apply_patch"

    @property
    def description(self) -> str:
        return (
            "Apply a unified diff patch to one or more files. The patch should be in "
            "standard unified diff format (like output of 'diff -u' or 'git diff'). "
            "Each file section starts with '--- a/path' and '+++ b/path' headers."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "patch": {
                    "type": "string",
                    "description": "The unified diff patch content.",
                },
            },
            "required": ["patch"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        patch_text = arguments.get("patch", "")
        if not patch_text:
            return ToolResult.text("Error: patch is required.", is_error=True)

        try:
            file_patches = _parse_unified_diff(patch_text)
        except ValueError as e:
            return ToolResult.text(f"Error parsing patch: {e}", is_error=True)

        if not file_patches:
            return ToolResult.text("Error: no file changes found in patch.", is_error=True)

        results: list[str] = []
        errors: list[str] = []

        for fp in file_patches:
            target = fp["target"]
            path = _resolve_path(target, self._workspace_root)
            if err := _check_path_safety(path, self._workspace_root):
                errors.append(f"{target}: {err}")
                continue

            try:
                if fp.get("is_new"):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(fp["new_content"], encoding="utf-8")
                    results.append(f"Created {target}")
                elif fp.get("is_delete"):
                    if path.exists():
                        path.unlink()
                        results.append(f"Deleted {target}")
                    else:
                        errors.append(f"{target}: file not found for deletion")
                else:
                    if not path.exists():
                        errors.append(f"{target}: file not found")
                        continue
                    content = path.read_text(encoding="utf-8")
                    new_content = _apply_hunks(content, fp["hunks"])
                    path.write_text(new_content, encoding="utf-8")
                    results.append(f"Patched {target} ({len(fp['hunks'])} hunk(s))")
            except Exception as e:
                errors.append(f"{target}: {e}")

        output_parts: list[str] = []
        if results:
            output_parts.append("Applied:\n" + "\n".join(f"  {r}" for r in results))
        if errors:
            output_parts.append("Errors:\n" + "\n".join(f"  {e}" for e in errors))

        is_error = len(errors) > 0 and len(results) == 0
        return ToolResult.text("\n".join(output_parts), is_error=is_error)


def _parse_unified_diff(text: str) -> list[dict[str, Any]]:
    """Parse unified diff into per-file patch structures."""
    patches: list[dict[str, Any]] = []
    lines = text.splitlines(keepends=True)
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith("--- "):
            src = _strip_diff_prefix(line[4:].strip())
            i += 1
            if i < len(lines) and lines[i].startswith("+++ "):
                dst = _strip_diff_prefix(lines[i][4:].strip())
                i += 1

                is_new = src == "/dev/null"
                is_delete = dst == "/dev/null"
                target = dst if not is_delete else src

                hunks: list[dict[str, Any]] = []
                new_lines: list[str] = []

                while i < len(lines):
                    if lines[i].startswith("--- "):
                        break

                    hunk_match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", lines[i])
                    if hunk_match:
                        old_start = int(hunk_match.group(1))
                        i += 1
                        removes: list[str] = []
                        adds: list[str] = []
                        context: list[str] = []

                        while i < len(lines):
                            ln = lines[i]
                            if ln.startswith("--- ") or ln.startswith("@@ "):
                                break
                            if ln.startswith("-"):
                                removes.append(ln[1:])
                            elif ln.startswith("+"):
                                adds.append(ln[1:])
                                if is_new:
                                    new_lines.append(ln[1:])
                            elif ln.startswith(" "):
                                context.append(ln[1:])
                            else:
                                pass  # "\ No newline at end of file" etc.
                            i += 1

                        hunks.append(
                            {
                                "old_start": old_start,
                                "removes": removes,
                                "adds": adds,
                                "context": context,
                            }
                        )
                    else:
                        i += 1

                patch: dict[str, Any] = {"target": target, "hunks": hunks}
                if is_new:
                    patch["is_new"] = True
                    patch["new_content"] = "".join(new_lines)
                elif is_delete:
                    patch["is_delete"] = True

                patches.append(patch)
            else:
                i += 1
        else:
            i += 1

    return patches


def _strip_diff_prefix(path: str) -> str:
    """Remove 'a/' or 'b/' prefix from diff paths."""
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def _apply_hunks(content: str, hunks: list[dict[str, Any]]) -> str:
    """Apply hunks to file content using line-based matching."""
    lines = content.splitlines(keepends=True)
    offset = 0

    for hunk in hunks:
        old_start = hunk["old_start"] - 1 + offset
        removes = hunk["removes"]
        adds = hunk["adds"]

        # Find the actual position by matching remove lines
        found_at = -1
        for search_pos in range(max(0, old_start - 5), min(len(lines), old_start + 10)):
            if _lines_match(lines, search_pos, removes):
                found_at = search_pos
                break

        if found_at == -1:
            # Fallback: just try the expected position
            found_at = old_start

        # Apply: remove old lines, insert new ones
        end = found_at + len(removes)
        lines[found_at:end] = adds
        offset += len(adds) - len(removes)

    return "".join(lines)


def _lines_match(lines: list[str], start: int, removes: list[str]) -> bool:
    if start + len(removes) > len(lines):
        return False
    return all(lines[start + i].rstrip("\n") == r.rstrip("\n") for i, r in enumerate(removes))
