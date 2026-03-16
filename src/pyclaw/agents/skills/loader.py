"""Skill loading — discover and parse SKILL.md files from multiple sources."""

from __future__ import annotations

import logging
import os
import re
import shutil
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from pyclaw.agents.skills.types import (
    SkillEntry,
    SkillInvocationPolicy,
    SkillMetadata,
    SkillRuntimeContract,
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
    config: dict[str, Any] | None = None,
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
                runtime_contract = _parse_runtime_contract(frontmatter, config=config)

                entries.append(
                    SkillEntry(
                        path=str(fpath),
                        name=name,
                        content=body,
                        frontmatter=frontmatter,
                        metadata=metadata,
                        invocation=_parse_invocation(frontmatter),
                        runtime_contract=runtime_contract,
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

    Load order: bundled < global < workspace.
    """
    _ = config  # reserved for future source toggles
    all_entries: list[SkillEntry] = []

    for source_dir, source_label in resolve_skill_source_dirs(workspace_dir):
        if source_dir.is_dir():
            all_entries.extend(load_skill_entries(source_dir, source=source_label, config=config))

    # Deduplicate by skill key, later entries override earlier
    seen: dict[str, SkillEntry] = {}
    for entry in all_entries:
        seen[entry.name] = entry

    return list(seen.values())


def resolve_skill_source_dirs(workspace_dir: str | Path) -> list[tuple[Path, str]]:
    """Return all known skill source directories in load order."""
    workspace = Path(workspace_dir)
    candidates: list[tuple[Path, str]] = []

    bundled = _resolve_bundled_skills_dir()
    if bundled:
        candidates.append((bundled, "bundled"))

    for p in _resolve_global_skill_dirs():
        candidates.append((p, "global"))

    candidates.extend(
        [
            (workspace / ".skills", "workspace"),
            (workspace / ".cursor" / "skills", "workspace"),
            (workspace / ".agents" / "skills", "workspace"),
        ]
    )

    deduped: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for path, source in candidates:
        norm = path.resolve() if path.exists() else path
        if norm in seen:
            continue
        seen.add(norm)
        deduped.append((path, source))
    return deduped


def _resolve_bundled_skills_dir() -> Path | None:
    """Find the bundled skills directory in the pyclaw package."""
    try:
        override = os.environ.get("PYCLAW_BUNDLED_SKILLS", "").strip()
        if override:
            override_dir = Path(override).expanduser()
            if override_dir.is_dir():
                return override_dir

        pkg_root = Path(__file__).resolve().parents[2]
        bundled = pkg_root / "bundled_skills"
        if bundled.is_dir():
            return bundled

        # Dev fallback for editable installs from repository root.
        repo_skills = Path(__file__).resolve().parents[4] / "skills"
        if repo_skills.is_dir():
            return repo_skills
    except Exception:
        pass
    return None


def _resolve_global_skill_dirs() -> list[Path]:
    """Resolve global skill directories for pyclaw/openclaw compatible layouts."""
    try:
        from pyclaw.config.paths import resolve_state_dir

        state_dir = resolve_state_dir()
        candidates = [
            state_dir / "skills",
            state_dir / "workspace" / "skills",
        ]
        # Also read openclaw-style global skills when running from ~/.pyclaw.
        if state_dir.name != ".openclaw":
            openclaw_state = Path.home() / ".openclaw"
            candidates.extend(
                [
                    openclaw_state / "skills",
                    openclaw_state / "workspace" / "skills",
                ]
            )
        return candidates
    except Exception:
        return []


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
    install_cmd = frontmatter.get("install", frontmatter.get("installCommand", "")).strip()
    install = {"command": install_cmd} if install_cmd else {}
    return SkillMetadata(
        skill_key=frontmatter.get("skill_key", frontmatter.get("skillKey", "")),
        always=frontmatter.get("always", "").lower() == "true",
        primary_env=frontmatter.get("primary_env", frontmatter.get("primaryEnv", "")),
        emoji=frontmatter.get("emoji", ""),
        homepage=frontmatter.get("homepage", ""),
        os_filter=_parse_list(frontmatter.get("os", "")),
        requires=_parse_list(frontmatter.get("requires", "")),
        install=install,
    )


def _parse_invocation(frontmatter: dict[str, str]) -> SkillInvocationPolicy:
    return SkillInvocationPolicy(
        user_invocable=frontmatter.get("userInvocable", "true").lower() != "false",
        disable_model_invocation=frontmatter.get("disableModelInvocation", "false").lower() == "true",
    )


def _parse_runtime_contract(
    frontmatter: dict[str, str],
    *,
    config: dict[str, Any] | None = None,
) -> SkillRuntimeContract:
    """Parse runtime contract and resolve dependency compatibility."""
    runtime = (frontmatter.get("runtime", "python-native") or "python-native").strip().lower()
    if runtime not in {"python-native", "node-wrapper", "mcp-bridge"}:
        runtime = "python-native"

    launcher = (frontmatter.get("launcher", runtime) or runtime).strip().lower()
    security_level = (
        (frontmatter.get("security-level", frontmatter.get("securityLevel", "standard")) or "standard").strip().lower()
    )
    if security_level not in {"standard", "elevated", "restricted"}:
        security_level = "standard"

    deps = _parse_list(
        frontmatter.get(
            "deps",
            frontmatter.get("dependencies", frontmatter.get("runtimeDeps", "")),
        )
    )

    # Runtime implied dependencies
    if runtime == "node-wrapper" and not any(d in {"cmd:node", "node"} for d in deps):
        deps.append("cmd:node")

    missing = _resolve_missing_deps(deps, config=config)
    return SkillRuntimeContract(
        runtime=runtime,
        launcher=launcher,
        security_level=security_level,
        deps=deps,
        missing_deps=missing,
        is_compatible=not missing,
    )


def _resolve_missing_deps(
    deps: list[str],
    *,
    config: dict[str, Any] | None = None,
) -> list[str]:
    """Return unresolved dependencies for a skill contract."""
    missing: list[str] = []
    for dep in deps:
        if not _is_dep_available(dep, config=config):
            missing.append(dep)
    return missing


def _is_dep_available(dep: str, *, config: dict[str, Any] | None = None) -> bool:
    dep = dep.strip()
    if not dep:
        return True

    if dep.startswith("cmd:"):
        binary = dep.split(":", 1)[1].strip()
        return bool(binary and shutil.which(binary))

    if dep.startswith("env:"):
        key = dep.split(":", 1)[1].strip()
        return bool(key and os.environ.get(key))

    if dep.startswith("py:"):
        module = dep.split(":", 1)[1].strip()
        return bool(module and find_spec(module) is not None)

    if dep.startswith("mcp:"):
        # mcp:<server-name> checks configured mcpServers by key.
        if not config:
            return True
        server_name = dep.split(":", 1)[1].strip()
        if not server_name:
            return False
        tools = config.get("tools") if isinstance(config, dict) else None
        if not isinstance(tools, dict):
            return False
        mcp_servers = tools.get("mcpServers")
        return isinstance(mcp_servers, dict) and server_name in mcp_servers

    # Bare token fallback: treat as command name for compatibility.
    return bool(shutil.which(dep))


def _parse_list(value: str) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]
