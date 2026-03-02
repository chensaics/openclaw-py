"""Tool policy — group-scoped tool allow/deny, plugin allowlist, escalation.

Ported from ``src/agents/tool-policy.ts`` and ``tool-policy-pipeline.ts``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

OWNER_ONLY_TOOLS = frozenset({
    "whatsapp_login",
    "cron",
    "gateway",
    "nodes",
    "exec",
    "process",
})

# Built-in tool groups
TOOL_GROUPS: dict[str, list[str]] = {
    "group:file": ["read", "write", "edit", "apply_patch", "grep", "find", "ls"],
    "group:exec": ["exec", "process"],
    "group:web": ["web_fetch", "web_search"],
    "group:memory": ["memory_search", "memory_get"],
    "group:session": ["sessions_list", "sessions_send", "sessions_spawn", "session_status"],
    "group:subagent": ["subagents", "agents_list"],
    "group:browser": ["browser"],
    "group:media": ["tts", "image"],
    "group:cron": ["cron"],
}


@dataclass
class ToolPolicy:
    """An allow/deny policy for tools."""
    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)
    also_allow: list[str] = field(default_factory=list)


def expand_tool_groups(names: list[str]) -> list[str]:
    """Expand group references (``group:xxx``) in a tool name list."""
    result: list[str] = []
    for name in names:
        if name in TOOL_GROUPS:
            result.extend(TOOL_GROUPS[name])
        else:
            result.append(name)
    return result


def expand_plugin_groups(
    names: list[str],
    plugin_tool_groups: dict[str, list[str]] | None = None,
) -> list[str]:
    """Expand plugin-specific group references."""
    groups = plugin_tool_groups or {}
    result: list[str] = []
    for name in names:
        if name == "group:plugins":
            for tools in groups.values():
                result.extend(tools)
        elif name in groups:
            result.extend(groups[name])
        else:
            result.append(name)
    return result


def _is_plugin_only_allowlist(
    allow: list[str],
    plugin_tool_groups: dict[str, list[str]] | None = None,
) -> bool:
    """Check if allowlist contains only plugin entries (no core tools)."""
    groups = plugin_tool_groups or {}
    all_plugin_tools: set[str] = set()
    for tools in groups.values():
        all_plugin_tools.update(tools)

    for name in allow:
        if name == "group:plugins" or name in groups:
            continue
        if name not in all_plugin_tools:
            return False
    return bool(allow)


def merge_policies(*policies: ToolPolicy | None) -> ToolPolicy:
    """Merge multiple policies — later policies override earlier ones.

    ``also_allow`` is additive. ``deny`` overrides ``allow``.
    """
    merged = ToolPolicy()
    for p in policies:
        if p is None:
            continue
        if p.allow:
            merged.allow = list(p.allow)
        if p.deny:
            merged.deny.extend(p.deny)
        if p.also_allow:
            merged.also_allow.extend(p.also_allow)
    return merged


def resolve_tool_policy(
    tool_names: list[str],
    policy: ToolPolicy,
    plugin_tool_groups: dict[str, list[str]] | None = None,
) -> list[str]:
    """Apply *policy* to filter *tool_names*, returning allowed tools."""
    expanded_allow = expand_tool_groups(expand_plugin_groups(policy.allow, plugin_tool_groups))
    expanded_deny = expand_tool_groups(expand_plugin_groups(policy.deny, plugin_tool_groups))
    expanded_also_allow = expand_tool_groups(expand_plugin_groups(policy.also_allow, plugin_tool_groups))

    # Strip plugin-only allowlists so core tools remain available
    if expanded_allow and _is_plugin_only_allowlist(policy.allow, plugin_tool_groups):
        expanded_allow = []

    deny_set = set(expanded_deny)
    allow_set = set(expanded_allow) if expanded_allow else None
    also_set = set(expanded_also_allow)

    result: list[str] = []
    for name in tool_names:
        if name in deny_set:
            continue
        if allow_set is not None:
            if name in allow_set or name in also_set:
                result.append(name)
        else:
            result.append(name)

    # Add also_allow tools not already present
    for name in expanded_also_allow:
        if name not in result and name not in deny_set:
            result.append(name)

    return result


def apply_owner_only_policy(
    tool_names: list[str],
    is_owner: bool,
    extra_owner_only: set[str] | None = None,
) -> list[str]:
    """Remove owner-only tools when the sender is not the owner."""
    if is_owner:
        return tool_names
    restricted = OWNER_ONLY_TOOLS | (extra_owner_only or set())
    return [t for t in tool_names if t not in restricted]
