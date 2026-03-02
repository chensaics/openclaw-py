"""ACP event mapper — translate between ACP prompt events and gateway events.

Ported from ``src/acp/event-mapper.ts``.
"""

from __future__ import annotations

from typing import Any


def extract_text_from_prompt(prompt: Any) -> str:
    """Extract plain text from an ACP prompt (string or content parts)."""
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, list):
        parts: list[str] = []
        for part in prompt:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "text" or part.get("type") == "input_text":
                    parts.append(str(part.get("text", "")))
        return "\n".join(parts) if parts else ""
    return str(prompt) if prompt else ""


def extract_attachments_from_prompt(prompt: Any) -> list[dict[str, Any]]:
    """Extract image/file attachments from an ACP prompt's content parts."""
    attachments: list[dict[str, Any]] = []
    if not isinstance(prompt, list):
        return attachments
    for part in prompt:
        if not isinstance(part, dict):
            continue
        ptype = part.get("type")
        if ptype in ("image", "input_image"):
            attachments.append({"type": "image", "source": part.get("source")})
        elif ptype in ("file", "input_file"):
            attachments.append({"type": "file", "source": part.get("source")})
    return attachments


def format_tool_title(name: str, args: dict[str, Any] | None = None) -> str:
    """Format a tool call title for display."""
    if not args:
        return name
    arg_str = ", ".join(f"{k}={_short(v)}" for k, v in sorted(args.items())[:3])
    return f"{name}({arg_str})"


def infer_tool_kind(name: str) -> str:
    """Infer tool kind from name for display purposes."""
    read_prefixes = ("read", "get", "list", "search", "find", "grep", "ls")
    if name.startswith(read_prefixes):
        return "read"
    write_prefixes = ("write", "create", "update", "delete", "apply_patch", "mkdir")
    if name.startswith(write_prefixes):
        return "write"
    exec_prefixes = ("exec", "run", "bash", "shell")
    if name.startswith(exec_prefixes):
        return "exec"
    return "tool"


def _short(v: Any, max_len: int = 40) -> str:
    s = str(v)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."
