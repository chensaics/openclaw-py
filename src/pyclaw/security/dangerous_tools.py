"""Dangerous tool marking, skill scanning, and external content policy.

Ported from ``src/security/dangerous-tools.ts``, ``src/security/skill-scanner.ts``,
and ``src/security/external-content.ts``.

Provides:
- Dangerous tool registry with risk categories
- Skill file scanning for unsafe patterns
- External content safety policy (URL fetch, file reads)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dangerous tool registry
# ---------------------------------------------------------------------------

class RiskCategory(str, Enum):
    EXEC = "exec"            # Code/command execution
    FILE_WRITE = "file_write"  # File system writes
    NETWORK = "network"      # Network access
    CREDENTIAL = "credential"  # Credential access
    DESTRUCTIVE = "destructive"  # Irreversible destructive actions
    PRIVACY = "privacy"      # Access to private/sensitive data


@dataclass
class DangerousToolDef:
    """Definition of a dangerous tool with risk metadata."""

    tool_name: str
    risk_categories: list[RiskCategory]
    description: str = ""
    requires_approval: bool = False
    max_risk_level: int = 1  # 1=low, 2=medium, 3=high


_DANGEROUS_TOOLS_REGISTRY: dict[str, DangerousToolDef] = {
    "system_run": DangerousToolDef(
        tool_name="system_run",
        risk_categories=[RiskCategory.EXEC],
        description="Execute shell commands",
        requires_approval=True,
        max_risk_level=3,
    ),
    "file_write": DangerousToolDef(
        tool_name="file_write",
        risk_categories=[RiskCategory.FILE_WRITE],
        description="Write files to disk",
        requires_approval=True,
        max_risk_level=2,
    ),
    "file_delete": DangerousToolDef(
        tool_name="file_delete",
        risk_categories=[RiskCategory.FILE_WRITE, RiskCategory.DESTRUCTIVE],
        description="Delete files from disk",
        requires_approval=True,
        max_risk_level=3,
    ),
    "web_fetch": DangerousToolDef(
        tool_name="web_fetch",
        risk_categories=[RiskCategory.NETWORK],
        description="Fetch content from URLs",
        max_risk_level=1,
    ),
    "web_search": DangerousToolDef(
        tool_name="web_search",
        risk_categories=[RiskCategory.NETWORK],
        description="Search the web",
        max_risk_level=1,
    ),
    "node_system_run": DangerousToolDef(
        tool_name="node_system_run",
        risk_categories=[RiskCategory.EXEC],
        description="Execute commands on remote nodes",
        requires_approval=True,
        max_risk_level=3,
    ),
}


def is_tool_dangerous(tool_name: str) -> bool:
    """Check if a tool is in the dangerous registry."""
    return tool_name in _DANGEROUS_TOOLS_REGISTRY


def get_tool_risk(tool_name: str) -> DangerousToolDef | None:
    """Get risk metadata for a tool."""
    return _DANGEROUS_TOOLS_REGISTRY.get(tool_name)


def get_all_dangerous_tools() -> dict[str, DangerousToolDef]:
    """Get all registered dangerous tools."""
    return dict(_DANGEROUS_TOOLS_REGISTRY)


def register_dangerous_tool(tool_def: DangerousToolDef) -> None:
    """Register a custom dangerous tool."""
    _DANGEROUS_TOOLS_REGISTRY[tool_def.tool_name] = tool_def


def requires_approval(tool_name: str) -> bool:
    """Check if a tool requires explicit user approval."""
    tool = _DANGEROUS_TOOLS_REGISTRY.get(tool_name)
    return tool.requires_approval if tool else False


def filter_tools_by_risk(
    tool_names: list[str],
    *,
    max_risk_level: int = 3,
    exclude_categories: list[RiskCategory] | None = None,
) -> list[str]:
    """Filter a tool list, removing tools above risk threshold or in excluded categories."""
    result: list[str] = []
    excluded = set(exclude_categories or [])

    for name in tool_names:
        tool = _DANGEROUS_TOOLS_REGISTRY.get(name)
        if tool is None:
            result.append(name)
            continue

        if tool.max_risk_level > max_risk_level:
            continue

        if excluded and any(cat in excluded for cat in tool.risk_categories):
            continue

        result.append(name)

    return result


# ---------------------------------------------------------------------------
# Skill file scanner
# ---------------------------------------------------------------------------

@dataclass
class SkillScanFinding:
    """A finding from scanning a skill file."""

    file_path: str
    line_number: int
    pattern: str
    severity: str  # "warning" | "critical"
    detail: str


_UNSAFE_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"(?:eval|exec)\s*\(", re.IGNORECASE), "critical", "eval/exec call detected"),
    (re.compile(r"subprocess\.", re.IGNORECASE), "warning", "subprocess usage detected"),
    (re.compile(r"os\.system\s*\(", re.IGNORECASE), "critical", "os.system call detected"),
    (re.compile(r"__import__\s*\(", re.IGNORECASE), "warning", "dynamic import detected"),
    (re.compile(r"rm\s+-rf\s+/", re.IGNORECASE), "critical", "destructive rm -rf detected"),
    (re.compile(r"curl\s+.*\|\s*(?:bash|sh)", re.IGNORECASE), "critical", "pipe to shell detected"),
    (re.compile(r"(?:api[_-]?key|secret|password|token)\s*[=:]\s*['\"][^'\"]+['\"]", re.IGNORECASE), "warning", "potential hardcoded secret"),
]


def scan_skill_file(path: str | Path) -> list[SkillScanFinding]:
    """Scan a skill file for unsafe patterns.

    Returns a list of findings. An empty list means the file is clean.
    """
    path = Path(path)
    findings: list[SkillScanFinding] = []

    if not path.exists() or not path.is_file():
        return findings

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings

    for line_num, line in enumerate(content.splitlines(), 1):
        for pattern, severity, detail in _UNSAFE_PATTERNS:
            if pattern.search(line):
                findings.append(SkillScanFinding(
                    file_path=str(path),
                    line_number=line_num,
                    pattern=pattern.pattern,
                    severity=severity,
                    detail=detail,
                ))

    return findings


def scan_skill_directory(directory: str | Path) -> list[SkillScanFinding]:
    """Scan all skill files in a directory."""
    directory = Path(directory)
    findings: list[SkillScanFinding] = []

    if not directory.exists() or not directory.is_dir():
        return findings

    for path in directory.rglob("*.md"):
        findings.extend(scan_skill_file(path))

    for path in directory.rglob("*.py"):
        findings.extend(scan_skill_file(path))

    return findings


# ---------------------------------------------------------------------------
# External content policy
# ---------------------------------------------------------------------------

class ExternalContentAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    SANITIZE = "sanitize"


@dataclass
class ExternalContentPolicy:
    """Policy for handling external content (URLs, fetched files)."""

    allow_url_fetch: bool = True
    allow_file_read: bool = True
    max_fetch_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    blocked_domains: list[str] = field(default_factory=list)
    blocked_schemes: list[str] = field(default_factory=lambda: ["file", "ftp"])
    allow_data_urls: bool = False
    strip_scripts: bool = True
    strip_iframes: bool = True

    def check_url(self, url: str) -> ExternalContentAction:
        """Check if a URL is allowed by this policy."""
        if not self.allow_url_fetch:
            return ExternalContentAction.BLOCK

        url_lower = url.lower().strip()

        # Block disallowed schemes
        for scheme in self.blocked_schemes:
            if url_lower.startswith(f"{scheme}:"):
                return ExternalContentAction.BLOCK

        # Block data URLs unless allowed
        if url_lower.startswith("data:") and not self.allow_data_urls:
            return ExternalContentAction.BLOCK

        # Block listed domains
        for domain in self.blocked_domains:
            if domain in url_lower:
                return ExternalContentAction.BLOCK

        # Sanitize if we need to strip scripts/iframes
        if self.strip_scripts or self.strip_iframes:
            return ExternalContentAction.SANITIZE

        return ExternalContentAction.ALLOW

    def check_file_path(self, path: str) -> ExternalContentAction:
        """Check if a file read is allowed."""
        if not self.allow_file_read:
            return ExternalContentAction.BLOCK

        return ExternalContentAction.ALLOW


def sanitize_html_content(html: str, *, policy: ExternalContentPolicy | None = None) -> str:
    """Sanitize HTML content according to the external content policy."""
    p = policy or ExternalContentPolicy()
    result = html

    if p.strip_scripts:
        result = re.sub(r"<script[^>]*>.*?</script>", "", result, flags=re.DOTALL | re.IGNORECASE)
        result = re.sub(r"<script[^>]*/>", "", result, flags=re.IGNORECASE)

    if p.strip_iframes:
        result = re.sub(r"<iframe[^>]*>.*?</iframe>", "", result, flags=re.DOTALL | re.IGNORECASE)
        result = re.sub(r"<iframe[^>]*/>", "", result, flags=re.IGNORECASE)

    # Strip event handlers
    result = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', "", result, flags=re.IGNORECASE)

    # Strip javascript: URLs
    result = re.sub(r'(?:href|src)\s*=\s*["\']javascript:[^"\']*["\']', "", result, flags=re.IGNORECASE)

    return result
