"""Extra bundled hooks — boot-md, bootstrap-extra-files, command-logger.

Ported from ``src/hooks/bundled/*.ts``.

Provides:
- Boot-md: startup checklist verification from BOOT.md
- Bootstrap-extra-files: workspace file loading into system prompt
- Command-logger: command execution logging to file
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Boot-MD Hook
# ---------------------------------------------------------------------------

@dataclass
class BootCheckItem:
    """A single check item from BOOT.md."""
    description: str
    check_type: str = "file_exists"  # file_exists | env_set | command_available
    target: str = ""
    required: bool = True
    passed: bool = False
    error: str = ""


@dataclass
class BootCheckResult:
    """Result of running boot checks."""
    items: list[BootCheckItem] = field(default_factory=list)
    all_passed: bool = False
    total: int = 0
    passed_count: int = 0
    failed_count: int = 0


def parse_boot_md(content: str) -> list[BootCheckItem]:
    """Parse a BOOT.md file into check items.

    Expected format:
    - [ ] Check description | check_type | target
    - [x] Already done check
    """
    items: list[BootCheckItem] = []
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith("- ["):
            continue

        checked = line.startswith("- [x]") or line.startswith("- [X]")
        text = line[5:].strip() if checked else line[5:].strip()

        parts = [p.strip() for p in text.split("|")]
        description = parts[0]
        check_type = parts[1] if len(parts) > 1 else "file_exists"
        target = parts[2] if len(parts) > 2 else ""

        items.append(BootCheckItem(
            description=description,
            check_type=check_type,
            target=target,
            passed=checked,
        ))

    return items


def run_boot_checks(
    items: list[BootCheckItem],
    *,
    workspace_dir: str = ".",
) -> BootCheckResult:
    """Run boot checks and return results."""
    import os
    import shutil

    for item in items:
        if item.passed:
            continue

        try:
            if item.check_type == "file_exists":
                path = Path(workspace_dir) / item.target if item.target else None
                item.passed = path.exists() if path else False
                if not item.passed:
                    item.error = f"File not found: {item.target}"

            elif item.check_type == "env_set":
                item.passed = bool(os.environ.get(item.target, ""))
                if not item.passed:
                    item.error = f"Environment variable not set: {item.target}"

            elif item.check_type == "command_available":
                item.passed = shutil.which(item.target) is not None
                if not item.passed:
                    item.error = f"Command not found: {item.target}"

        except Exception as e:
            item.error = str(e)

    passed = sum(1 for i in items if i.passed)
    failed = sum(1 for i in items if not i.passed and i.required)

    return BootCheckResult(
        items=items,
        all_passed=failed == 0,
        total=len(items),
        passed_count=passed,
        failed_count=failed,
    )


# ---------------------------------------------------------------------------
# Bootstrap Extra Files Hook
# ---------------------------------------------------------------------------

@dataclass
class ExtraFileSpec:
    """Specification for a workspace file to load."""
    path: str
    label: str = ""
    max_size_bytes: int = 50000
    optional: bool = True


def load_extra_files(
    specs: list[ExtraFileSpec],
    *,
    workspace_dir: str = ".",
) -> list[tuple[str, str]]:
    """Load workspace files for system prompt enrichment.

    Returns list of (label, content) tuples.
    """
    results: list[tuple[str, str]] = []

    for spec in specs:
        path = Path(workspace_dir) / spec.path
        if not path.exists():
            if not spec.optional:
                logger.warning("Required extra file not found: %s", spec.path)
            continue

        try:
            content = path.read_text(encoding="utf-8")
            if len(content) > spec.max_size_bytes:
                content = content[:spec.max_size_bytes] + "\n...(truncated)"
            label = spec.label or spec.path
            results.append((label, content))
        except Exception:
            logger.debug("Failed to read extra file: %s", spec.path, exc_info=True)

    return results


def format_extra_files_for_prompt(files: list[tuple[str, str]]) -> str:
    """Format loaded files for injection into system prompt."""
    if not files:
        return ""

    parts: list[str] = ["\n---\nWorkspace files:"]
    for label, content in files:
        parts.append(f"\n### {label}\n```\n{content}\n```")

    return "\n".join(parts)


# Default file specs for common workspace files
DEFAULT_EXTRA_FILES: list[ExtraFileSpec] = [
    ExtraFileSpec("AGENTS.md", "Agent Instructions"),
    ExtraFileSpec("CLAUDE.md", "Agent Instructions"),
    ExtraFileSpec("RULES.md", "Project Rules"),
    ExtraFileSpec(".cursorrules", "Cursor Rules"),
    ExtraFileSpec("README.md", "README", max_size_bytes=20000),
]


# ---------------------------------------------------------------------------
# Command Logger Hook
# ---------------------------------------------------------------------------

@dataclass
class CommandLogEntry:
    """A logged command execution."""
    command: str
    args: list[str] = field(default_factory=list)
    working_dir: str = ""
    exit_code: int | None = None
    started_at: float = 0.0
    finished_at: float = 0.0
    session_id: str = ""
    agent_id: str = ""

    def __post_init__(self) -> None:
        if self.started_at == 0:
            self.started_at = time.time()

    @property
    def duration_s(self) -> float:
        if not self.finished_at:
            return 0.0
        return self.finished_at - self.started_at

    def to_log_line(self) -> str:
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(self.started_at))
        code = str(self.exit_code) if self.exit_code is not None else "?"
        cmd = self.command
        if self.args:
            cmd += " " + " ".join(self.args)
        return f"[{ts}] exit={code} dur={self.duration_s:.1f}s cmd={cmd}"


class CommandLogger:
    """Log command executions to file and memory."""

    def __init__(self, *, log_file: str = "", max_entries: int = 1000) -> None:
        self._entries: list[CommandLogEntry] = []
        self._log_file = log_file
        self._max_entries = max_entries

    def log(self, entry: CommandLogEntry) -> None:
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries.pop(0)

        if self._log_file:
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write(entry.to_log_line() + "\n")
            except OSError:
                logger.debug("Failed to write command log", exc_info=True)

    def recent(self, n: int = 20) -> list[CommandLogEntry]:
        return self._entries[-n:]

    @property
    def total_logged(self) -> int:
        return len(self._entries)
