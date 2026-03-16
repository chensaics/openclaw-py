"""Skill prompt building — assemble skills into the agent system prompt."""

from __future__ import annotations

import platform
from typing import Any

from pyclaw.agents.skills.loader import load_workspace_skill_entries
from pyclaw.agents.skills.types import SkillEntry, SkillSnapshot

_MAX_SKILLS_IN_PROMPT = 50
_MAX_SKILLS_PROMPT_CHARS = 100_000


def build_workspace_skills_prompt(
    workspace_dir: str,
    *,
    config: dict[str, Any] | None = None,
    skill_filter: list[str] | None = None,
    max_skills: int = _MAX_SKILLS_IN_PROMPT,
    max_chars: int = _MAX_SKILLS_PROMPT_CHARS,
) -> SkillSnapshot:
    """Build a skills snapshot and prompt for the agent system prompt."""
    entries = load_workspace_skill_entries(workspace_dir, config=config)

    # Filter by eligibility
    eligible = [e for e in entries if _is_eligible(e)]

    # Apply skill filter if provided
    if skill_filter is not None:
        eligible = [e for e in eligible if e.name in skill_filter]

    # Sort: always-on first, then alphabetical
    eligible.sort(key=lambda e: (not e.metadata.always, e.name))

    # Limit count
    selected = eligible[:max_skills]

    # Build prompt
    prompt_parts: list[str] = []
    total_chars = 0

    for entry in selected:
        section = _format_skill_section(entry)
        if total_chars + len(section) > max_chars:
            break
        prompt_parts.append(section)
        total_chars += len(section)

    prompt = "\n\n".join(prompt_parts) if prompt_parts else ""

    return SkillSnapshot(
        prompt=prompt,
        skills=selected,
        skill_filter=skill_filter,
        resolved_skills=[e.name for e in selected],
        version=1,
    )


def resolve_skills_prompt_for_run(
    workspace_dir: str | None = None,
    *,
    config: dict[str, Any] | None = None,
) -> str:
    """Resolve the skills prompt text for an agent run."""
    if not workspace_dir:
        return ""

    snapshot = build_workspace_skills_prompt(workspace_dir, config=config)
    return snapshot.prompt


def _is_eligible(entry: SkillEntry) -> bool:
    """Check if a skill is eligible for the current platform."""
    if not entry.runtime_contract.is_compatible:
        return False

    if entry.metadata.os_filter:
        current_os = platform.system().lower()
        os_map = {"darwin": "macos", "linux": "linux", "windows": "windows"}
        normalized = os_map.get(current_os, current_os)
        if normalized not in [o.lower() for o in entry.metadata.os_filter]:
            return False

    return not entry.invocation.disable_model_invocation


def _format_skill_section(entry: SkillEntry) -> str:
    """Format a single skill entry for the system prompt."""
    header = f"### Skill: {entry.name}"
    if entry.metadata.emoji:
        header = f"### {entry.metadata.emoji} Skill: {entry.name}"

    parts = [header]
    if entry.content.strip():
        parts.append(entry.content.strip())
    else:
        parts.append(f"(Skill file at: {entry.path})")

    return "\n".join(parts)
