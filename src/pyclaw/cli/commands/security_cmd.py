"""CLI security subcommands — audit, check."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import typer

from pyclaw.config.io import load_config_raw
from pyclaw.config.paths import resolve_config_path, resolve_state_dir


@dataclass
class AuditFinding:
    category: str
    severity: str  # info | warning | error
    message: str
    fix_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
        }
        if self.fix_hint:
            d["fixHint"] = self.fix_hint
        return d


def security_audit_command(
    *,
    deep: bool = False,
    fix: bool = False,
    output_json: bool = False,
) -> None:
    """Audit the configuration and environment for security weaknesses."""
    findings: list[AuditFinding] = []

    config_path = resolve_config_path()
    if not config_path.exists():
        findings.append(AuditFinding(
            category="config",
            severity="info",
            message="No configuration file found — nothing to audit.",
        ))
    else:
        raw = load_config_raw(config_path)
        _audit_config(raw, findings, deep=deep)

    _audit_state_dir(findings)
    _audit_environment(findings)

    if deep:
        _audit_deep(findings)

    if fix:
        _apply_fixes(findings, config_path)

    if output_json:
        typer.echo(json.dumps({
            "findings": [f.to_dict() for f in findings],
            "errors": sum(1 for f in findings if f.severity == "error"),
            "warnings": sum(1 for f in findings if f.severity == "warning"),
            "info": sum(1 for f in findings if f.severity == "info"),
        }, ensure_ascii=False))
        return

    if not findings:
        typer.echo("Security audit: no issues found.")
        return

    for f in findings:
        icon = {"error": "x", "warning": "!", "info": "i"}.get(f.severity, "?")
        typer.echo(f"  [{icon}] [{f.category}] {f.message}")
        if f.fix_hint:
            typer.echo(f"      Fix: {f.fix_hint}")

    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    typer.echo(f"\n{errors} error(s), {warnings} warning(s).")


def _audit_config(raw: dict[str, Any], findings: list[AuditFinding], *, deep: bool) -> None:
    config_str = json.dumps(raw)

    # Plaintext API keys
    if "sk-" in config_str and "apiKey" in config_str:
        findings.append(AuditFinding(
            category="secrets",
            severity="warning",
            message="Possible plaintext API key in config (sk-... pattern detected).",
            fix_hint="Use env variable references: \"apiKey\": \"${ANTHROPIC_API_KEY}\"",
        ))

    # Gateway bound to all interfaces
    gw = raw.get("gateway", {})
    if isinstance(gw, dict) and gw.get("bind") == "0.0.0.0":
        findings.append(AuditFinding(
            category="gateway",
            severity="warning",
            message="Gateway bound to all interfaces (0.0.0.0).",
            fix_hint="Bind to 127.0.0.1 unless remote access is intended.",
        ))

    # No auth configured on gateway
    gw_auth = gw.get("auth", {}) if isinstance(gw, dict) else {}
    if isinstance(gw_auth, dict):
        has_auth = gw_auth.get("password") or gw_auth.get("token")
        if not has_auth:
            findings.append(AuditFinding(
                category="gateway",
                severity="info",
                message="No gateway authentication configured.",
                fix_hint="Set gateway.auth.password or gateway.auth.token for remote use.",
            ))

    # Exec tool unrestricted
    tools = raw.get("tools", {})
    if isinstance(tools, dict):
        exec_cfg = tools.get("exec", {})
        if isinstance(exec_cfg, dict) and exec_cfg.get("enabled") is True:
            if not exec_cfg.get("allowlist") and not exec_cfg.get("denylist"):
                findings.append(AuditFinding(
                    category="tools",
                    severity="warning",
                    message="Exec tool enabled without allowlist/denylist.",
                    fix_hint="Add tools.exec.allowlist or tools.exec.denylist.",
                ))


def _audit_state_dir(findings: list[AuditFinding]) -> None:
    import os
    state_dir = resolve_state_dir()
    if state_dir.exists() and not os.access(str(state_dir), os.W_OK):
        findings.append(AuditFinding(
            category="filesystem",
            severity="error",
            message=f"State directory not writable: {state_dir}",
        ))


def _audit_environment(findings: list[AuditFinding]) -> None:
    import os
    # Check for leaked API keys in environment display
    sensitive_vars = [
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
        "OPENROUTER_API_KEY", "PYCLAW_AUTH_TOKEN",
    ]
    for var in sensitive_vars:
        val = os.environ.get(var, "")
        if val and not val.startswith("${"):
            findings.append(AuditFinding(
                category="environment",
                severity="info",
                message=f"Environment variable {var} is set (ensure it is not logged).",
            ))


def _audit_deep(findings: list[AuditFinding]) -> None:
    """Additional deep checks."""
    import os
    config_path = resolve_config_path()
    if config_path.exists():
        # Check file permissions
        mode = config_path.stat().st_mode & 0o777
        if mode & 0o044:
            findings.append(AuditFinding(
                category="filesystem",
                severity="info",
                message=f"Config file is world/group readable (mode {oct(mode)}).",
                fix_hint=f"chmod 600 {config_path}",
            ))


def _apply_fixes(findings: list[AuditFinding], config_path: Path) -> None:
    """Auto-fix what we can: file permissions, gateway bind address."""
    import os
    import stat

    fixed = 0

    for f in findings:
        if (
            f.category == "filesystem"
            and "world/group readable" in f.message
            and config_path.exists()
        ):
            try:
                config_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
                f.message += " [FIXED: chmod 600]"
                fixed += 1
            except OSError:
                pass

        if (
            f.category == "gateway"
            and "0.0.0.0" in f.message
            and config_path.exists()
        ):
            try:
                text = config_path.read_text(encoding="utf-8")
                if '"0.0.0.0"' in text:
                    text = text.replace('"0.0.0.0"', '"127.0.0.1"')
                    config_path.write_text(text, encoding="utf-8")
                    f.message += " [FIXED: rebound to 127.0.0.1]"
                    fixed += 1
            except OSError:
                pass

    if fixed:
        typer.echo(f"\nAuto-fixed {fixed} issue(s).")
