"""Skill loading — discover and parse SKILL.md files from multiple sources."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from pyclaw.agents.skills.types import (
    SkillEntry,
    SkillInvocationPolicy,
    SkillMetadata,
)

logger = logging.getLogger(__name__)

_SKILL_FILENAME = "SKILL.md"
_MAX_SKILL_FILE_BYTES = 32_768
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def load_skill_entries(
    skill_dir: str | Path,
    *,
    source: str = "workspace",
    max_file_bytes: int = _MAX_SKILL_FILE_BYTES,
) -> list[SkillEntry]:
    """Load all SKILL.md files from a directory tree."""
    skill_dir = Path(skill_dir)
    if not skill_dir.is_dir():
        return []

    entries: list[SkillEntry] = []
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv"}

    for dirpath, dirnames, filenames in os.walk(skill_dir):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fname in filenames:
            if fname != _SKILL_FILENAME:
                continue

            fpath = Path(dirpath) / fname
            try:
                size = fpath.stat().st_size
                if size > max_file_bytes:
                    logger.debug("Skipping oversized skill: %s (%d bytes)", fpath, size)
                    continue

                content = fpath.read_text(encoding="utf-8")
                frontmatter, body = _parse_frontmatter(content)
                metadata = _parse_metadata(frontmatter)
                name = metadata.skill_key or fpath.parent.name

                entries.append(
                    SkillEntry(
                        path=str(fpath),
                        name=name,
                        content=body,
                        frontmatter=frontmatter,
                        metadata=metadata,
                        invocation=_parse_invocation(frontmatter),
                        source=source,
                    )
                )
            except (OSError, UnicodeDecodeError) as e:
                logger.debug("Error loading skill %s: %s", fpath, e)

    return entries


def load_workspace_skill_entries(
    workspace_dir: str | Path,
    *,
    config: dict[str, Any] | None = None,
) -> list[SkillEntry]:
    """Load skills from all configured sources in priority order.

    Load order: bundled < managed < agents-skills < workspace
    """
    workspace_dir = Path(workspace_dir)
    all_entries: list[SkillEntry] = []

    # Workspace-level skills
    workspace_skills = workspace_dir / ".skills"
    if workspace_skills.is_dir():
        all_entries.extend(load_skill_entries(workspace_skills, source="workspace"))

    # Cursor-style skills
    cursor_skills = workspace_dir / ".cursor" / "skills"
    if cursor_skills.is_dir():
        all_entries.extend(load_skill_entries(cursor_skills, source="workspace"))

    # Agent-level skills
    agent_skills = workspace_dir / ".agents" / "skills"
    if agent_skills.is_dir():
        all_entries.extend(load_skill_entries(agent_skills, source="workspace"))

    # Bundled skills from the pyclaw installation
    bundled = _resolve_bundled_skills_dir()
    if bundled and bundled.is_dir():
        all_entries.extend(load_skill_entries(bundled, source="bundled"))

    # Deduplicate by skill key, later entries override earlier
    seen: dict[str, SkillEntry] = {}
    for entry in all_entries:
        seen[entry.name] = entry

    return list(seen.values())


def _resolve_bundled_skills_dir() -> Path | None:
    """Find the bundled skills directory in the pyclaw package."""
    try:
        pkg_dir = Path(__file__).parent.parent
        bundled = pkg_dir / "templates"
        if bundled.is_dir():
            return bundled
    except Exception:
        pass
    return None


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML-like frontmatter from skill content."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content

    fm_text = match.group(1)
    body = content[match.end() :]
    fm: dict[str, str] = {}

    for line in fm_text.splitlines():
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()

    return fm, body


def _parse_metadata(frontmatter: dict[str, str]) -> SkillMetadata:
    """Parse skill metadata from frontmatter."""
    return SkillMetadata(
        skill_key=frontmatter.get("skill_key", frontmatter.get("skillKey", "")),
        always=frontmatter.get("always", "").lower() == "true",
        primary_env=frontmatter.get("primary_env", frontmatter.get("primaryEnv", "")),
        emoji=frontmatter.get("emoji", ""),
        homepage=frontmatter.get("homepage", ""),
        os_filter=_parse_list(frontmatter.get("os", "")),
        requires=_parse_list(frontmatter.get("requires", "")),
    )


def _parse_invocation(frontmatter: dict[str, str]) -> SkillInvocationPolicy:
    return SkillInvocationPolicy(
        user_invocable=frontmatter.get("userInvocable", "true").lower() != "false",
        disable_model_invocation=frontmatter.get("disableModelInvocation", "false").lower() == "true",
    )


def _parse_list(value: str) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]
