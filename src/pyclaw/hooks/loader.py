"""Discover and load hooks from HOOK.md files."""

from __future__ import annotations

import importlib
import logging
import re
from pathlib import Path

from pyclaw.hooks.registry import register_hook
from pyclaw.hooks.types import HookEntry, HookEntryMeta

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str | list[str]]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    result: dict[str, str | list[str]] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            items = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
            result[key] = items
        else:
            result[key] = val
    return result


def load_hook_entries(directory: Path) -> list[HookEntry]:
    """Scan *directory* for ``HOOK.md`` files and return parsed entries."""
    entries: list[HookEntry] = []
    if not directory.is_dir():
        return entries

    for hook_md in directory.rglob("HOOK.md"):
        try:
            text = hook_md.read_text(encoding="utf-8")
        except OSError:
            continue

        fm = _parse_frontmatter(text)
        _events = fm.get("events")
        _requires = fm.get("requires")
        events: list[str] = _events if isinstance(_events, list) else ([_events] if isinstance(_events, str) else [])
        requires: list[str] = _requires if isinstance(_requires, list) else ([_requires] if isinstance(_requires, str) else [])
        meta = HookEntryMeta(
            name=str(fm.get("name", hook_md.parent.name)),
            events=events,
            requires=requires,
            description=str(fm.get("description", "")),
            module=str(fm.get("module", "")),
        )
        entries.append(HookEntry(meta=meta))
    return entries


def load_workspace_hooks(directories: list[Path]) -> list[HookEntry]:
    """Load hooks from multiple directories and register them."""
    all_entries: list[HookEntry] = []
    for d in directories:
        entries = load_hook_entries(d)
        for entry in entries:
            if entry.meta.module:
                try:
                    mod = importlib.import_module(entry.meta.module)
                    handler = getattr(mod, "handle", None) or getattr(mod, "handler", None)
                    if handler:
                        entry.handler = handler
                        for event_key in entry.meta.events:
                            register_hook(event_key, handler)
                except Exception:
                    logger.exception("Failed to load hook module %s", entry.meta.module)
        all_entries.extend(entries)
    return all_entries
