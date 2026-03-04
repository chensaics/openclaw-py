"""Doctor diagnostic flows — config/auth/sandbox/gateway/workspace/memory/state/security/platform.

Ported from ``src/commands/doctor*.ts``.

Provides:
- Modular diagnostic checks for each subsystem
- Fix suggestions with actionable commands
- Summary report with severity levels
- Pluggable check registry
"""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(str, Enum):
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class DiagnosticResult:
    """Result of a single diagnostic check."""

    check_name: str
    category: str
    severity: Severity = Severity.OK
    message: str = ""
    fix_hint: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagnosticReport:
    """Full diagnostic report."""

    results: list[DiagnosticResult] = field(default_factory=list)
    platform: str = ""
    python_version: str = ""

    @property
    def has_errors(self) -> bool:
        return any(r.severity in (Severity.ERROR, Severity.CRITICAL) for r in self.results)

    @property
    def has_warnings(self) -> bool:
        return any(r.severity == Severity.WARNING for r in self.results)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.severity in (Severity.ERROR, Severity.CRITICAL))

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if r.severity == Severity.WARNING)

    def by_category(self) -> dict[str, list[DiagnosticResult]]:
        categories: dict[str, list[DiagnosticResult]] = {}
        for r in self.results:
            categories.setdefault(r.category, []).append(r)
        return categories

    def summary_text(self) -> str:
        lines = [f"Doctor Report — {len(self.results)} checks"]
        lines.append(f"  Platform: {self.platform}")
        lines.append(f"  Python: {self.python_version}")
        lines.append(f"  Errors: {self.error_count}, Warnings: {self.warning_count}")
        for cat, results in self.by_category().items():
            lines.append(f"\n  [{cat}]")
            for r in results:
                icon = {"ok": "✓", "info": "ℹ", "warning": "⚠", "error": "✗", "critical": "✗✗"}.get(
                    r.severity.value, "?"
                )
                lines.append(f"    {icon} {r.check_name}: {r.message}")
                if r.fix_hint:
                    lines.append(f"      Fix: {r.fix_hint}")
        return "\n".join(lines)


DiagnosticCheck = Callable[[], DiagnosticResult]


class DiagnosticRegistry:
    """Registry of diagnostic checks."""

    def __init__(self) -> None:
        self._checks: list[DiagnosticCheck] = []

    def register(self, check: DiagnosticCheck) -> None:
        self._checks.append(check)

    def run_all(self) -> DiagnosticReport:
        report = DiagnosticReport(
            platform=sys.platform,
            python_version=sys.version.split()[0],
        )
        for check in self._checks:
            try:
                result = check()
                report.results.append(result)
            except Exception as e:
                report.results.append(
                    DiagnosticResult(
                        check_name=getattr(check, "__name__", "unknown"),
                        category="internal",
                        severity=Severity.ERROR,
                        message=f"Check failed: {e}",
                    )
                )
        return report


# ---------------------------------------------------------------------------
# Built-in Checks
# ---------------------------------------------------------------------------


def check_config() -> DiagnosticResult:
    """Check config file exists and is valid JSON."""
    config_path = Path.home() / ".pyclaw" / "config.json"
    if not config_path.exists():
        return DiagnosticResult(
            check_name="config_file",
            category="config",
            severity=Severity.WARNING,
            message="Config file not found",
            fix_hint="Run 'pyclaw setup' to create initial config",
        )
    try:
        import json

        json.loads(config_path.read_text(encoding="utf-8"))
        return DiagnosticResult(
            check_name="config_file",
            category="config",
            severity=Severity.OK,
            message="Config file is valid JSON",
        )
    except json.JSONDecodeError as e:
        return DiagnosticResult(
            check_name="config_file",
            category="config",
            severity=Severity.ERROR,
            message=f"Config file has invalid JSON: {e}",
            fix_hint="Fix the JSON syntax in ~/.pyclaw/config.json",
        )


def check_auth() -> DiagnosticResult:
    """Check that at least one LLM provider is configured."""
    creds_dir = Path.home() / ".pyclaw" / "credentials"
    if not creds_dir.exists():
        return DiagnosticResult(
            check_name="auth_credentials",
            category="auth",
            severity=Severity.WARNING,
            message="No credentials directory found",
            fix_hint="Run 'pyclaw auth login' to configure a provider",
        )
    cred_files = list(creds_dir.iterdir())
    if not cred_files:
        return DiagnosticResult(
            check_name="auth_credentials",
            category="auth",
            severity=Severity.WARNING,
            message="No provider credentials found",
            fix_hint="Run 'pyclaw auth login' to configure a provider",
        )
    return DiagnosticResult(
        check_name="auth_credentials",
        category="auth",
        severity=Severity.OK,
        message=f"{len(cred_files)} credential file(s) found",
    )


def check_sandbox() -> DiagnosticResult:
    """Check sandbox directory access."""
    home = Path.home() / ".pyclaw"
    if not home.exists():
        return DiagnosticResult(
            check_name="sandbox_dir",
            category="sandbox",
            severity=Severity.WARNING,
            message="pyclaw home directory not found",
            fix_hint="Run 'pyclaw setup' to initialize",
        )
    if not os.access(str(home), os.W_OK):
        return DiagnosticResult(
            check_name="sandbox_dir",
            category="sandbox",
            severity=Severity.ERROR,
            message="pyclaw home directory is not writable",
            fix_hint=f"Check permissions on {home}",
        )
    return DiagnosticResult(
        check_name="sandbox_dir",
        category="sandbox",
        severity=Severity.OK,
        message="Sandbox directory is accessible",
    )


def check_gateway_connectivity() -> DiagnosticResult:
    """Check if gateway port is reachable on localhost."""
    import socket as sock

    port = 18789
    try:
        s = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(("127.0.0.1", port))
        s.close()
        if result == 0:
            return DiagnosticResult(
                check_name="gateway_port",
                category="gateway",
                severity=Severity.OK,
                message=f"Gateway is listening on port {port}",
            )
        return DiagnosticResult(
            check_name="gateway_port",
            category="gateway",
            severity=Severity.INFO,
            message=f"Gateway not running on port {port}",
            fix_hint="Start the gateway with 'pyclaw gateway run'",
        )
    except Exception as e:
        return DiagnosticResult(
            check_name="gateway_port",
            category="gateway",
            severity=Severity.WARNING,
            message=f"Gateway check failed: {e}",
        )


def check_workspace() -> DiagnosticResult:
    """Check current workspace for .pyclaw/ or skills."""
    cwd = Path.cwd()
    local_dir = cwd / ".pyclaw"
    if local_dir.exists():
        return DiagnosticResult(
            check_name="workspace",
            category="workspace",
            severity=Severity.OK,
            message=f"Workspace config at {local_dir}",
        )
    return DiagnosticResult(
        check_name="workspace",
        category="workspace",
        severity=Severity.INFO,
        message="No local .pyclaw/ directory in workspace",
    )


def check_memory() -> DiagnosticResult:
    """Check memory store accessibility."""
    mem_dir = Path.home() / ".pyclaw" / "memory"
    if not mem_dir.exists():
        return DiagnosticResult(
            check_name="memory_store",
            category="memory",
            severity=Severity.INFO,
            message="No memory store found (will be created on first use)",
        )
    db_files = list(mem_dir.glob("*.db")) + list(mem_dir.glob("*.sqlite"))
    return DiagnosticResult(
        check_name="memory_store",
        category="memory",
        severity=Severity.OK,
        message=f"Memory store with {len(db_files)} database(s)",
    )


def check_state() -> DiagnosticResult:
    """Check session state directory."""
    sessions_dir = Path.home() / ".pyclaw" / "sessions"
    if not sessions_dir.exists():
        return DiagnosticResult(
            check_name="session_state",
            category="state",
            severity=Severity.INFO,
            message="No sessions directory (will be created on first use)",
        )
    count = sum(1 for _ in sessions_dir.iterdir() if _.is_dir())
    return DiagnosticResult(
        check_name="session_state",
        category="state",
        severity=Severity.OK,
        message=f"{count} session(s) found",
    )


def check_platform() -> DiagnosticResult:
    """Check platform-specific notes."""
    notes: list[str] = []

    if sys.platform == "darwin":
        if shutil.which("launchctl"):
            notes.append("macOS: launchctl available")
    elif sys.platform == "linux":
        if shutil.which("systemctl"):
            notes.append("Linux: systemctl available")

    if shutil.which("tailscale"):
        notes.append("Tailscale CLI available")

    return DiagnosticResult(
        check_name="platform_notes",
        category="platform",
        severity=Severity.OK,
        message="; ".join(notes) if notes else f"Platform: {sys.platform}",
    )


def check_security() -> DiagnosticResult:
    """Basic security audit."""
    config_path = Path.home() / ".pyclaw" / "config.json"
    if not config_path.exists():
        return DiagnosticResult(
            check_name="security_audit",
            category="security",
            severity=Severity.INFO,
            message="No config to audit",
        )
    try:
        import json

        config = json.loads(config_path.read_text(encoding="utf-8"))
        issues: list[str] = []

        # Check for plaintext API keys in config
        config_str = json.dumps(config)
        if "sk-" in config_str and "api_key" in config_str:
            issues.append("Possible plaintext API key in config (consider using secrets)")

        gateway = config.get("gateway", {})
        if gateway.get("bind") == "0.0.0.0":
            issues.append("Gateway bound to all interfaces (consider loopback)")

        if issues:
            return DiagnosticResult(
                check_name="security_audit",
                category="security",
                severity=Severity.WARNING,
                message=f"{len(issues)} issue(s): {'; '.join(issues)}",
            )

        return DiagnosticResult(
            check_name="security_audit",
            category="security",
            severity=Severity.OK,
            message="No security issues detected",
        )
    except Exception:
        return DiagnosticResult(
            check_name="security_audit",
            category="security",
            severity=Severity.INFO,
            message="Could not parse config for audit",
        )


BUILTIN_CHECKS: list[DiagnosticCheck] = [
    check_config,
    check_auth,
    check_sandbox,
    check_gateway_connectivity,
    check_workspace,
    check_memory,
    check_state,
    check_security,
    check_platform,
]


def create_default_registry() -> DiagnosticRegistry:
    """Create a registry with all built-in checks."""
    registry = DiagnosticRegistry()
    for check in BUILTIN_CHECKS:
        registry.register(check)
    return registry


def run_doctor() -> DiagnosticReport:
    """Run all diagnostic checks and return a report."""
    registry = create_default_registry()
    return registry.run_all()
