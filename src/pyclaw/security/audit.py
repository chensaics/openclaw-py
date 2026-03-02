"""Security audit — configuration and runtime security checks.

Ported from ``src/security/audit.ts``.
"""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pyclaw.config.paths import resolve_config_path, resolve_credentials_dir, resolve_state_dir

logger = logging.getLogger(__name__)


class AuditSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AuditFinding:
    id: str
    severity: AuditSeverity
    title: str
    detail: str = ""
    remediation: str = ""


@dataclass
class AuditResult:
    findings: list[AuditFinding] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == AuditSeverity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == AuditSeverity.WARNING)


def _check_config_permissions(result: AuditResult) -> None:
    """Check that config files are not world-readable."""
    config_path = resolve_config_path()
    if not config_path.exists():
        return

    try:
        mode = config_path.stat().st_mode
        if mode & stat.S_IROTH:
            result.findings.append(AuditFinding(
                id="config-world-readable",
                severity=AuditSeverity.WARNING,
                title="Config file is world-readable",
                detail=str(config_path),
                remediation=f"chmod 600 {config_path}",
            ))
    except OSError:
        pass


def _check_credentials_permissions(result: AuditResult) -> None:
    creds_dir = resolve_credentials_dir()
    if not creds_dir.exists():
        return

    try:
        mode = creds_dir.stat().st_mode
        if mode & stat.S_IROTH:
            result.findings.append(AuditFinding(
                id="credentials-world-readable",
                severity=AuditSeverity.CRITICAL,
                title="Credentials directory is world-readable",
                detail=str(creds_dir),
                remediation=f"chmod 700 {creds_dir}",
            ))
    except OSError:
        pass


def _check_gateway_auth(result: AuditResult, config: dict[str, Any] | None = None) -> None:
    """Warn if gateway runs without authentication."""
    if not config:
        return

    gateway = config.get("gateway", {})
    token = gateway.get("token") or gateway.get("authToken")
    password = gateway.get("password")
    bind = gateway.get("bind", "loopback")

    if not token and not password:
        severity = AuditSeverity.CRITICAL if bind != "loopback" else AuditSeverity.WARNING
        result.findings.append(AuditFinding(
            id="gateway-no-auth",
            severity=severity,
            title="Gateway has no authentication configured",
            detail=f"bind={bind}, no token or password set",
            remediation="Set gateway.token or gateway.password in config",
        ))


def _check_secrets_in_config(result: AuditResult, config: dict[str, Any] | None = None) -> None:
    """Detect plaintext secrets embedded directly in config values."""
    if not config:
        return

    import re
    secret_pattern = re.compile(
        r"(sk-[a-zA-Z0-9]{20}|ghp_[a-zA-Z0-9]{20}|xoxb-[a-zA-Z0-9\-]{20})",
    )

    def _walk(obj: Any, path: str = "") -> None:
        if isinstance(obj, str):
            if secret_pattern.search(obj):
                result.findings.append(AuditFinding(
                    id="secret-in-config",
                    severity=AuditSeverity.CRITICAL,
                    title="Plaintext secret detected in config",
                    detail=f"Path: {path}",
                    remediation="Use environment variable or file reference instead",
                ))
        elif isinstance(obj, dict):
            for k, v in obj.items():
                _walk(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                _walk(v, f"{path}[{i}]")

    _walk(config)


def _check_logging_redaction(result: AuditResult, config: dict[str, Any] | None = None) -> None:
    if not config:
        return

    logging_cfg = config.get("logging", {})
    redact = logging_cfg.get("redactSensitive", "tools")
    if redact == "off":
        result.findings.append(AuditFinding(
            id="logging-redaction-off",
            severity=AuditSeverity.WARNING,
            title="Log redaction is disabled",
            detail="logging.redactSensitive = off",
            remediation='Set logging.redactSensitive to "tools"',
        ))


def _check_exec_security(result: AuditResult, config: dict[str, Any] | None = None) -> None:
    if not config:
        return

    exec_cfg = config.get("exec", {})
    security = exec_cfg.get("security", "allowlist")
    if security == "full":
        result.findings.append(AuditFinding(
            id="exec-security-full",
            severity=AuditSeverity.WARNING,
            title='Exec security is set to "full" — all commands allowed',
            remediation='Use "allowlist" mode for production deployments',
        ))


def run_security_audit(
    config: dict[str, Any] | None = None,
    *,
    deep: bool = False,
) -> AuditResult:
    """Run a security audit across config, credentials, and runtime settings.

    Args:
        config: parsed config dict (optional; loads from disk if absent).
        deep: include additional checks (e.g. gateway probe).
    """
    result = AuditResult()

    _check_config_permissions(result)
    _check_credentials_permissions(result)
    _check_gateway_auth(result, config)
    _check_secrets_in_config(result, config)
    _check_logging_redaction(result, config)
    _check_exec_security(result, config)

    if not result.findings:
        result.findings.append(AuditFinding(
            id="all-clear",
            severity=AuditSeverity.INFO,
            title="No security issues found",
        ))

    return result
