"""Update checker — version comparison and channel resolution.

Ported from ``src/infra/update-check.ts`` and ``src/infra/update-channels.ts``.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

UpdateChannel = Literal["stable", "beta", "dev"]


@dataclass
class GitUpdateStatus:
    branch: str = ""
    tag: str = ""
    is_dirty: bool = False
    ahead: int = 0
    behind: int = 0
    commit: str = ""


@dataclass
class DepsStatus:
    ok: bool = True
    missing: list[str] = field(default_factory=list)


@dataclass
class RegistryStatus:
    latest_version: str = ""
    channel_tag: str = "latest"


@dataclass
class UpdateCheckResult:
    current_version: str = ""
    install_kind: str = ""  # "git" | "package" | "unknown"
    git: GitUpdateStatus | None = None
    deps: DepsStatus | None = None
    registry: RegistryStatus | None = None
    update_available: bool = False
    channel: UpdateChannel = "stable"


def _run_git(*args: str, cwd: str | None = None) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def detect_install_kind(project_dir: str | None = None) -> str:
    """Detect whether this is a git checkout or npm package install."""
    if project_dir and (Path(project_dir) / ".git").exists():
        return "git"
    try:
        import pyclaw

        pkg_path = Path(pyclaw.__file__).parent
        if (pkg_path.parent.parent / ".git").exists():
            return "git"
    except Exception:
        pass
    return "package"


def check_git_update_status(project_dir: str | None = None) -> GitUpdateStatus:
    status = GitUpdateStatus()
    cwd = project_dir

    branch = _run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    status.branch = branch or ""

    tag = _run_git("describe", "--tags", "--exact-match", "HEAD", cwd=cwd)
    status.tag = tag or ""

    commit = _run_git("rev-parse", "--short", "HEAD", cwd=cwd)
    status.commit = commit or ""

    dirty = _run_git("status", "--porcelain", cwd=cwd)
    status.is_dirty = bool(dirty)

    counts = _run_git("rev-list", "--left-right", "--count", "@{upstream}...HEAD", cwd=cwd)
    if counts:
        parts = counts.split()
        if len(parts) == 2:
            status.behind = int(parts[0])
            status.ahead = int(parts[1])

    return status


def resolve_effective_update_channel(
    git_status: GitUpdateStatus | None = None,
    config_channel: str | None = None,
) -> UpdateChannel:
    """Resolve the effective update channel from git state and config."""
    if config_channel and config_channel in ("stable", "beta", "dev"):
        return config_channel  # type: ignore[return-value]

    if git_status:
        if git_status.tag:
            if "beta" in git_status.tag:
                return "beta"
            return "stable"
        if git_status.branch == "main":
            return "dev"

    return "stable"


def channel_to_npm_tag(channel: UpdateChannel) -> str:
    return {"beta": "beta", "dev": "dev"}.get(channel, "latest")


def compare_semver(a: str, b: str) -> int:
    """Compare two version strings. Returns -1, 0, or 1."""

    def _parts(v: str) -> tuple[int, ...]:
        clean = re.sub(r"^v", "", v).split("-")[0]
        return tuple(int(x) for x in clean.split(".") if x.isdigit())

    pa, pb = _parts(a), _parts(b)
    if pa < pb:
        return -1
    if pa > pb:
        return 1
    return 0


def fetch_npm_tag_version(package: str = "pyclaw", tag: str = "latest") -> str | None:
    """Fetch the latest version from npm registry for a given tag."""
    try:
        result = subprocess.run(
            ["npm", "view", f"{package}@{tag}", "version", "--userconfig", "/dev/null"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def check_update_status(
    current_version: str = "",
    project_dir: str | None = None,
    config_channel: str | None = None,
) -> UpdateCheckResult:
    """Perform a full update status check."""
    result = UpdateCheckResult(current_version=current_version)
    result.install_kind = detect_install_kind(project_dir)

    if result.install_kind == "git":
        result.git = check_git_update_status(project_dir)
        result.channel = resolve_effective_update_channel(result.git, config_channel)
    else:
        result.channel = resolve_effective_update_channel(None, config_channel)

    npm_tag = channel_to_npm_tag(result.channel)
    latest = fetch_npm_tag_version(tag=npm_tag)
    if latest:
        result.registry = RegistryStatus(latest_version=latest, channel_tag=npm_tag)
        if current_version and compare_semver(current_version, latest) < 0:
            result.update_available = True

    return result
