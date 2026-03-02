"""Session-memory hook — saves recent session messages to a memory file.

On ``command:new`` or ``command:reset``, reads the most recent session
transcript, optionally uses an LLM to generate a slug, and writes a
Markdown file to ``workspace/memory/``.
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import Any

from pyclaw.hooks.types import HookEvent

logger = logging.getLogger(__name__)

DEFAULT_MESSAGE_COUNT = 20


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    return slug.strip("-")[:60]


def _build_markdown(messages: list[dict[str, Any]], session_key: str) -> str:
    lines = [f"# Session Memory: {session_key}", ""]
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
            content = "\n".join(text_parts)
        lines.append(f"**{role}**: {content}")
        lines.append("")
    return "\n".join(lines)


async def handle(event: HookEvent) -> None:
    """Handle command:new and command:reset events."""
    if event.action not in ("new", "reset"):
        return

    messages = event.messages
    if not messages:
        return

    workspace_dir = event.context.get("workspace_dir")
    if not workspace_dir:
        return

    memory_dir = Path(workspace_dir) / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    max_msgs = event.context.get("session_memory_messages", DEFAULT_MESSAGE_COUNT)
    recent = messages[-max_msgs:]

    session_key = event.session_key or "unknown"
    slug = _slugify(session_key)
    date_str = datetime.date.today().isoformat()
    filename = f"{date_str}-{slug}.md"

    content = _build_markdown(recent, session_key)
    (memory_dir / filename).write_text(content, encoding="utf-8")
    logger.info("Session memory saved: %s", filename)
