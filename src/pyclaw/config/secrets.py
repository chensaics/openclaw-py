"""Secret/credential management — SecretRef, providers, and resolution.

Ported from ``src/config/types.secrets.ts``, ``src/utils/normalize-secret-input.ts``,
and ``src/agents/model-auth.ts``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

SecretRefSource = Literal["env", "file", "exec"]

DEFAULT_SECRET_PROVIDER_ALIAS = "default"
_ENV_SECRET_TEMPLATE_RE = re.compile(r"^\$\{([A-Z][A-Z0-9_]{0,127})\}$")


@dataclass(frozen=True)
class SecretRef:
    """Stable identifier for a secret in a configured source."""
    source: SecretRefSource
    provider: str
    id: str


@dataclass(frozen=True)
class EnvSecretProvider:
    source: Literal["env"] = "env"
    allowlist: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FileSecretProvider:
    source: Literal["file"] = "file"
    path: str = ""
    mode: Literal["singleValue", "json"] = "singleValue"
    timeout_ms: int = 5000
    max_bytes: int = 1_048_576


@dataclass(frozen=True)
class ExecSecretProvider:
    source: Literal["exec"] = "exec"
    command: str = ""
    args: list[str] = field(default_factory=list)
    timeout_ms: int = 10_000
    max_output_bytes: int = 1_048_576
    json_only: bool = False
    env: dict[str, str] = field(default_factory=dict)


SecretProviderConfig = EnvSecretProvider | FileSecretProvider | ExecSecretProvider
SecretInput = str | SecretRef


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_secret_input(value: Any) -> str:
    """Strip line-break characters from copy-pasted credentials.

    Removes ``\\r``, ``\\n``, ``\\u2028``, ``\\u2029`` anywhere then trims.
    Does NOT remove internal spaces to preserve ``Bearer <token>`` values.
    """
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\r\n\u2028\u2029]+", "", value).strip()


def normalize_optional_secret_input(value: Any) -> str | None:
    normalized = normalize_secret_input(value)
    return normalized or None


# ---------------------------------------------------------------------------
# SecretRef helpers
# ---------------------------------------------------------------------------

def is_secret_ref(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if set(value.keys()) != {"source", "provider", "id"}:
        return False
    return (
        value.get("source") in ("env", "file", "exec")
        and isinstance(value.get("provider"), str)
        and len(value["provider"].strip()) > 0
        and isinstance(value.get("id"), str)
        and len(value["id"].strip()) > 0
    )


def parse_env_template(value: Any, provider: str = DEFAULT_SECRET_PROVIDER_ALIAS) -> SecretRef | None:
    """Parse ``${VAR_NAME}`` env-template strings into a SecretRef."""
    if not isinstance(value, str):
        return None
    m = _ENV_SECRET_TEMPLATE_RE.match(value.strip())
    if not m:
        return None
    return SecretRef(
        source="env",
        provider=provider.strip() or DEFAULT_SECRET_PROVIDER_ALIAS,
        id=m.group(1),
    )


def coerce_secret_ref(value: Any, defaults: dict[str, str] | None = None) -> SecretRef | None:
    """Try to interpret *value* as a ``SecretRef``."""
    defaults = defaults or {}
    if isinstance(value, SecretRef):
        return value
    if isinstance(value, dict):
        if is_secret_ref(value):
            return SecretRef(**value)
        src = value.get("source")
        vid = value.get("id")
        if src in ("env", "file", "exec") and isinstance(vid, str) and vid.strip():
            provider = defaults.get(src, DEFAULT_SECRET_PROVIDER_ALIAS)
            return SecretRef(source=src, provider=provider, id=vid)
    env_ref = parse_env_template(value, defaults.get("env", DEFAULT_SECRET_PROVIDER_ALIAS))
    if env_ref:
        return env_ref
    return None


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

# Known env var names per provider (from pi-ai's getEnvApiKey)
_PROVIDER_ENV_VARS: dict[str, list[str]] = {
    "anthropic": ["ANTHROPIC_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
    "gemini": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
    "together": ["TOGETHER_API_KEY"],
    "groq": ["GROQ_API_KEY"],
    "ollama": [],
    "amazon-bedrock": ["AWS_BEARER_TOKEN_BEDROCK", "AWS_ACCESS_KEY_ID"],
}


def resolve_env_api_key(provider: str) -> tuple[str, str] | None:
    """Check environment for a provider's API key. Returns ``(key, source)``."""
    env_vars = _PROVIDER_ENV_VARS.get(provider, [])
    for var in env_vars:
        val = os.environ.get(var, "").strip()
        if val:
            return val, f"env:{var}"
    return None


def resolve_secret_ref(ref: SecretRef, providers: dict[str, SecretProviderConfig] | None = None) -> str | None:
    """Resolve a ``SecretRef`` to its string value."""
    providers = providers or {}
    cfg = providers.get(ref.provider)

    if ref.source == "env":
        val = os.environ.get(ref.id, "").strip()
        if cfg and isinstance(cfg, EnvSecretProvider) and cfg.allowlist:
            if ref.id not in cfg.allowlist:
                return None
        return val or None

    if ref.source == "file":
        file_path = ref.id
        if cfg and isinstance(cfg, FileSecretProvider) and cfg.path:
            file_path = cfg.path
        p = Path(file_path).expanduser()
        if not p.is_file():
            return None
        content = p.read_text(encoding="utf-8").strip()
        if cfg and isinstance(cfg, FileSecretProvider) and cfg.mode == "json":
            try:
                data = json.loads(content)
                parts = ref.id.strip("/").split("/")
                for part in parts:
                    if isinstance(data, dict):
                        data = data.get(part)
                    else:
                        return None
                return str(data) if data is not None else None
            except (json.JSONDecodeError, TypeError):
                return None
        return content or None

    if ref.source == "exec":
        cmd = ref.id
        args: list[str] = []
        timeout = 10.0
        if cfg and isinstance(cfg, ExecSecretProvider):
            cmd = cfg.command or ref.id
            args = list(cfg.args)
            timeout = cfg.timeout_ms / 1000.0
        try:
            result = subprocess.run(
                [cmd, *args],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.stdout.strip() or None
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None

    return None


def resolve_api_key_for_provider(
    provider: str,
    *,
    config: dict[str, Any] | None = None,
) -> str | None:
    """Resolve an API key for *provider* from config or environment.

    Resolution order:
    1. ``models.providers.<provider>.apiKey`` in config
    2. Known environment variables for the provider
    """
    if config:
        providers_cfg = config.get("models", {}).get("providers", {})
        provider_cfg = providers_cfg.get(provider, {})
        raw_key = provider_cfg.get("apiKey")
        if raw_key:
            normalized = normalize_secret_input(raw_key)
            if normalized:
                return normalized

    env_result = resolve_env_api_key(provider)
    if env_result:
        return env_result[0]

    return None
