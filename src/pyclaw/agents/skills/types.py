"""Skill type definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillMetadata:
    """Metadata parsed from a SKILL.md frontmatter."""

    skill_key: str = ""
    always: bool = False
    primary_env: str = ""
    emoji: str = ""
    homepage: str = ""
    os_filter: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    install: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillInvocationPolicy:
    user_invocable: bool = True
    disable_model_invocation: bool = False


@dataclass
class SkillCommandSpec:
    name: str
    skill_name: str
    description: str = ""
    dispatch_tool: str = ""
    dispatch_arg_mode: str = ""


@dataclass
class SkillEntry:
    """A loaded skill with its content and metadata."""

    path: str = ""
    name: str = ""
    content: str = ""
    frontmatter: dict[str, str] = field(default_factory=dict)
    metadata: SkillMetadata = field(default_factory=SkillMetadata)
    invocation: SkillInvocationPolicy = field(default_factory=SkillInvocationPolicy)
    source: str = ""  # "workspace", "bundled", "managed", "plugin"


@dataclass
class SkillSnapshot:
    """Snapshot of skills available for an agent run."""

    prompt: str = ""
    skills: list[SkillEntry] = field(default_factory=list)
    skill_filter: list[str] | None = None
    resolved_skills: list[str] = field(default_factory=list)
    version: int = 0
