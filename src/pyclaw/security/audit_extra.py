"""Extended security audit — Gateway HTTP, plugins, hooks, and channels.

Ported from ``src/security/audit-extra*.ts`` and ``src/security/audit-channel.ts``.

Extends the base security audit with checks for:
- Gateway HTTP binding and TLS configuration
- Plugin trust and isolation
- Hook script permissions and sources
- Channel-level security (auth config, allowlist coherence)
"""

from __future__ import annotations

import logging
from typing import Any

from pyclaw.security.audit import AuditFinding, AuditResult, AuditSeverity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gateway HTTP audits
# ---------------------------------------------------------------------------


def audit_gateway_http(config: dict[str, Any]) -> list[AuditFinding]:
    """Audit gateway HTTP binding and TLS settings."""
    findings: list[AuditFinding] = []
    gateway = config.get("gateway", {})

    bind = gateway.get("bind", "loopback")
    port = gateway.get("port", 18789)
    tls = gateway.get("tls", {})
    tls_enabled = tls.get("enabled", False)

    # Non-loopback without TLS
    if bind not in ("loopback", "127.0.0.1", "localhost") and not tls_enabled:
        findings.append(
            AuditFinding(
                id="gateway-no-tls-nonlocal",
                severity=AuditSeverity.CRITICAL,
                title="Gateway exposed on network without TLS",
                detail=f"bind={bind}, port={port}, TLS disabled",
                remediation="Enable TLS or bind to loopback",
            )
        )

    # Weak TLS
    if tls_enabled:
        min_version = tls.get("minVersion", "")
        if min_version and min_version in ("TLSv1", "TLSv1.1"):
            findings.append(
                AuditFinding(
                    id="gateway-weak-tls",
                    severity=AuditSeverity.WARNING,
                    title=f"Gateway TLS minimum version is weak: {min_version}",
                    remediation="Set tls.minVersion to TLSv1.2 or higher",
                )
            )

    # CORS
    cors = gateway.get("cors", {})
    cors_origins = cors.get("origins", [])
    if "*" in cors_origins:
        findings.append(
            AuditFinding(
                id="gateway-cors-wildcard",
                severity=AuditSeverity.WARNING,
                title="Gateway CORS allows all origins",
                detail="cors.origins includes '*'",
                remediation="Restrict CORS origins to trusted domains",
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Plugin audits
# ---------------------------------------------------------------------------


def audit_plugins(config: dict[str, Any]) -> list[AuditFinding]:
    """Audit plugin configuration for trust and isolation issues."""
    findings: list[AuditFinding] = []
    plugins = config.get("plugins", {})

    if not isinstance(plugins, dict):
        return findings

    plugin_list = plugins.get("installed", plugins.get("list", []))
    if not isinstance(plugin_list, list):
        return findings

    for plugin in plugin_list:
        name = plugin if isinstance(plugin, str) else plugin.get("name", "")

        if isinstance(plugin, dict):
            # Check for elevated permissions
            permissions = plugin.get("permissions", [])
            if "exec" in permissions or "shell" in permissions:
                findings.append(
                    AuditFinding(
                        id=f"plugin-exec-permission-{name}",
                        severity=AuditSeverity.WARNING,
                        title=f"Plugin '{name}' has exec/shell permissions",
                        detail=f"Permissions: {permissions}",
                        remediation="Review plugin code and restrict permissions if possible",
                    )
                )

            # Check for network access
            if "network" in permissions:
                findings.append(
                    AuditFinding(
                        id=f"plugin-network-permission-{name}",
                        severity=AuditSeverity.INFO,
                        title=f"Plugin '{name}' has network permissions",
                    )
                )

            # Untrusted sources
            source = plugin.get("source", "")
            if source and not source.startswith(("npm:", "@pyclaw/", "pyclaw-")):
                findings.append(
                    AuditFinding(
                        id=f"plugin-untrusted-source-{name}",
                        severity=AuditSeverity.WARNING,
                        title=f"Plugin '{name}' is from an untrusted source",
                        detail=f"Source: {source}",
                        remediation="Verify the plugin source before deploying",
                    )
                )

    return findings


# ---------------------------------------------------------------------------
# Hook audits
# ---------------------------------------------------------------------------


def audit_hooks(config: dict[str, Any]) -> list[AuditFinding]:
    """Audit hook configurations for security issues."""
    findings: list[AuditFinding] = []
    hooks = config.get("hooks", {})

    if not isinstance(hooks, dict):
        return findings

    for hook_name, hook_config in hooks.items():
        if not isinstance(hook_config, dict):
            continue

        # Check for shell execution in hooks
        handler = hook_config.get("handler", "")
        if isinstance(handler, str) and any(p in handler for p in ["sh ", "bash ", "exec(", "eval(", "system("]):
            findings.append(
                AuditFinding(
                    id=f"hook-shell-exec-{hook_name}",
                    severity=AuditSeverity.CRITICAL,
                    title=f"Hook '{hook_name}' contains shell execution",
                    detail=f"Handler: {handler[:100]}",
                    remediation="Use script files with proper permissions instead",
                )
            )

        # Check for external URLs in hooks
        url = hook_config.get("url", "")
        if url and not url.startswith(("http://localhost", "http://127.0.0.1", "https://")):
            findings.append(
                AuditFinding(
                    id=f"hook-insecure-url-{hook_name}",
                    severity=AuditSeverity.WARNING,
                    title=f"Hook '{hook_name}' uses insecure HTTP URL",
                    detail=f"URL: {url}",
                    remediation="Use HTTPS for hook endpoints",
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Channel audits
# ---------------------------------------------------------------------------


def audit_channels(config: dict[str, Any]) -> list[AuditFinding]:
    """Audit channel configurations for security issues."""
    findings: list[AuditFinding] = []
    channels = config.get("channels", {})

    if not isinstance(channels, dict):
        return findings

    for channel_id, channel_config in channels.items():
        if not isinstance(channel_config, dict):
            continue

        # Open DM policy on non-ephemeral channels
        dm_policy = channel_config.get("dmPolicy", "allowlist")
        if dm_policy == "open":
            findings.append(
                AuditFinding(
                    id=f"channel-open-dm-{channel_id}",
                    severity=AuditSeverity.WARNING,
                    title=f"Channel '{channel_id}' has open DM policy",
                    detail="Anyone can message the bot",
                    remediation="Use 'allowlist' or 'pairing' DM policy",
                )
            )

        # No allowlist configured
        allow_from = channel_config.get("allowFrom", channel_config.get("allow_from"))
        if dm_policy == "allowlist" and not allow_from:
            findings.append(
                AuditFinding(
                    id=f"channel-empty-allowlist-{channel_id}",
                    severity=AuditSeverity.WARNING,
                    title=f"Channel '{channel_id}' has allowlist policy but no entries",
                    detail="No one can message the bot",
                    remediation="Add sender IDs to the allowFrom list",
                )
            )

        # Token/secret in plaintext
        for key in ("token", "bot_token", "app_secret", "api_key", "webhook_secret"):
            val = channel_config.get(key, "")
            if val and isinstance(val, str) and not val.startswith(("$", "env:", "secret:")):
                findings.append(
                    AuditFinding(
                        id=f"channel-plaintext-secret-{channel_id}-{key}",
                        severity=AuditSeverity.WARNING,
                        title=f"Channel '{channel_id}' has plaintext {key}",
                        remediation=f"Use environment variable reference for {key}",
                    )
                )

    return findings


# ---------------------------------------------------------------------------
# Run all extended audits
# ---------------------------------------------------------------------------


def run_extended_audit(config: dict[str, Any]) -> AuditResult:
    """Run all extended security audits.

    Complements the base ``run_security_audit`` with gateway HTTP,
    plugins, hooks, and channel-level checks.
    """
    result = AuditResult()

    result.findings.extend(audit_gateway_http(config))
    result.findings.extend(audit_plugins(config))
    result.findings.extend(audit_hooks(config))
    result.findings.extend(audit_channels(config))

    if not result.findings:
        result.findings.append(
            AuditFinding(
                id="extended-all-clear",
                severity=AuditSeverity.INFO,
                title="No extended security issues found",
            )
        )

    return result
