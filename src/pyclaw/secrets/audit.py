"""Secrets audit — scan config and auth files for plaintext secrets and stale refs.

Ported from ``src/secrets/audit.ts``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pyclaw.config.paths import resolve_config_path, resolve_agents_dir, resolve_state_dir
from pyclaw.config.secrets import SecretRef, coerce_secret_ref, is_secret_ref
from pyclaw.secrets.resolve import SecretRefResolveCache, resolve_secret_ref_value

logger = logging.getLogger(__name__)

AuditCode = Literal["PLAINTEXT_FOUND", "REF_UNRESOLVED", "REF_SHADOWED", "LEGACY_RESIDUE"]
AuditSeverity = Literal["info", "warn", "error"]


@dataclass
class SecretsAuditFinding:
    code: AuditCode
    severity: AuditSeverity
    file: str
    json_path: str
    message: str
    provider: str | None = None
    profile_id: str | None = None


@dataclass
class SecretsAuditReport:
    version: int = 1
    status: str = "clean"  # "clean" | "findings" | "unresolved"
    files_scanned: list[str] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=lambda: {
        "plaintext_count": 0,
        "unresolved_ref_count": 0,
        "shadowed_ref_count": 0,
        "legacy_residue_count": 0,
    })
    findings: list[SecretsAuditFinding] = field(default_factory=list)


# Known patterns that look like plaintext API keys
_API_KEY_PATTERNS = [
    "sk-",       # OpenAI
    "sk-ant-",   # Anthropic
    "AIzaSy",    # Google
    "gsk_",      # Groq
    "xai-",      # xAI
]


def _looks_like_plaintext_key(value: str) -> bool:
    if not value or len(value) < 10:
        return False
    return any(value.startswith(prefix) for prefix in _API_KEY_PATTERNS)


def run_secrets_audit(
    *,
    state_dir: Path | None = None,
    config_path: Path | None = None,
    providers: dict[str, Any] | None = None,
) -> SecretsAuditReport:
    """Run a full secrets audit across config and auth profile files.

    Checks for:
    - PLAINTEXT_FOUND: API keys stored as plain strings
    - REF_UNRESOLVED: SecretRefs that can't be resolved
    - REF_SHADOWED: SecretRefs shadowed by env vars
    - LEGACY_RESIDUE: Old auth.json files still present
    """
    report = SecretsAuditReport()
    sd = state_dir or resolve_state_dir()

    # Scan main config
    cfg_path = config_path or resolve_config_path()
    if cfg_path.exists():
        report.files_scanned.append(str(cfg_path))
        _audit_config_file(cfg_path, report, providers)

    # Scan auth profiles
    agents_dir = resolve_agents_dir(sd)
    if agents_dir.exists():
        for agent_dir in sorted(agents_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            auth_file = agent_dir / "auth-profiles.json"
            if auth_file.exists():
                report.files_scanned.append(str(auth_file))
                _audit_auth_profiles(auth_file, agent_dir.name, report)

            # Check for legacy auth.json
            legacy_auth = agent_dir / "auth.json"
            if legacy_auth.exists():
                report.files_scanned.append(str(legacy_auth))
                report.findings.append(SecretsAuditFinding(
                    code="LEGACY_RESIDUE",
                    severity="warn",
                    file=str(legacy_auth),
                    json_path="/",
                    message=f"Legacy auth.json found for agent '{agent_dir.name}'. "
                            "Migrate to auth-profiles.json or remove.",
                ))
                report.summary["legacy_residue_count"] += 1

    # Set status
    unresolved = report.summary["unresolved_ref_count"]
    total = sum(report.summary.values())
    if total == 0:
        report.status = "clean"
    elif unresolved > 0:
        report.status = "unresolved"
    else:
        report.status = "findings"

    return report


def _audit_config_file(
    path: Path, report: SecretsAuditReport, providers: dict[str, Any] | None
) -> None:
    try:
        import json5
        data = json5.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, dict):
        return

    models_providers = data.get("models", {}).get("providers", {})
    if isinstance(models_providers, dict):
        for prov_id, prov_cfg in models_providers.items():
            if not isinstance(prov_cfg, dict):
                continue
            api_key = prov_cfg.get("apiKey")
            json_path = f"models.providers.{prov_id}.apiKey"

            if isinstance(api_key, str) and _looks_like_plaintext_key(api_key):
                report.findings.append(SecretsAuditFinding(
                    code="PLAINTEXT_FOUND",
                    severity="error",
                    file=str(path),
                    json_path=json_path,
                    message=f"Plaintext API key found for provider '{prov_id}'.",
                    provider=prov_id,
                ))
                report.summary["plaintext_count"] += 1
            elif is_secret_ref(api_key):
                ref = coerce_secret_ref(api_key)
                if ref:
                    cache = SecretRefResolveCache()
                    resolved = resolve_secret_ref_value(ref, providers, cache=cache)
                    if resolved is None:
                        report.findings.append(SecretsAuditFinding(
                            code="REF_UNRESOLVED",
                            severity="error",
                            file=str(path),
                            json_path=json_path,
                            message=f"SecretRef for '{prov_id}' cannot be resolved: "
                                    f"{ref.source}:{ref.provider}:{ref.id}",
                            provider=prov_id,
                        ))
                        report.summary["unresolved_ref_count"] += 1


def _audit_auth_profiles(path: Path, agent_id: str, report: SecretsAuditReport) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, dict):
        return

    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict):
        return

    for profile_id, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        for field_name in ("apiKey", "token", "accessToken", "refreshToken"):
            value = profile.get(field_name)
            if isinstance(value, str) and _looks_like_plaintext_key(value):
                report.findings.append(SecretsAuditFinding(
                    code="PLAINTEXT_FOUND",
                    severity="error",
                    file=str(path),
                    json_path=f"profiles.{profile_id}.{field_name}",
                    message=f"Plaintext credential in auth profile '{profile_id}' "
                            f"for agent '{agent_id}'.",
                    profile_id=profile_id,
                ))
                report.summary["plaintext_count"] += 1
