"""Secret ref resolution — resolve SecretRefs to their actual values.

Ported from ``src/secrets/resolve.ts``.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from pyclaw.config.secrets import (
    EnvSecretProvider,
    ExecSecretProvider,
    FileSecretProvider,
    SecretProviderConfig,
    SecretRef,
)

logger = logging.getLogger(__name__)

DEFAULT_FILE_TIMEOUT_S = 5.0
DEFAULT_EXEC_TIMEOUT_S = 5.0
DEFAULT_MAX_OUTPUT_BYTES = 1_048_576


class SecretRefResolveCache:
    """Cache for resolved secret values, keyed by ref key."""

    def __init__(self) -> None:
        self._resolved: dict[str, str | None] = {}

    def get(self, ref: SecretRef) -> str | None:
        return self._resolved.get(_ref_key(ref))

    def has(self, ref: SecretRef) -> bool:
        return _ref_key(ref) in self._resolved

    def set(self, ref: SecretRef, value: str | None) -> None:
        self._resolved[_ref_key(ref)] = value

    def clear(self) -> None:
        self._resolved.clear()


def _ref_key(ref: SecretRef) -> str:
    return f"{ref.source}:{ref.provider}:{ref.id}"


def resolve_secret_ref_value(
    ref: SecretRef,
    providers: dict[str, SecretProviderConfig] | None = None,
    *,
    cache: SecretRefResolveCache | None = None,
    env: dict[str, str] | None = None,
) -> str | None:
    """Resolve a SecretRef to its string value.

    Uses provider config if available, falls back to direct resolution.
    """
    if cache and cache.has(ref):
        return cache.get(ref)

    result: str | None = None
    effective_env = env or dict(os.environ)
    provider_cfg = (providers or {}).get(ref.provider)

    if ref.source == "env":
        result = _resolve_env(ref, provider_cfg, effective_env)
    elif ref.source == "file":
        result = _resolve_file(ref, provider_cfg)
    elif ref.source == "exec":
        result = _resolve_exec(ref, provider_cfg)

    if cache:
        cache.set(ref, result)
    return result


def _resolve_env(ref: SecretRef, cfg: SecretProviderConfig | None, env: dict[str, str]) -> str | None:
    if cfg and isinstance(cfg, EnvSecretProvider) and cfg.allowlist and ref.id not in cfg.allowlist:
        return None
    return env.get(ref.id, "").strip() or None


def _resolve_file(ref: SecretRef, cfg: SecretProviderConfig | None) -> str | None:
    file_path = ref.id
    if cfg and isinstance(cfg, FileSecretProvider) and cfg.path:
        file_path = cfg.path

    p = Path(file_path).expanduser()
    if not p.is_file():
        return None

    try:
        max_bytes = cfg.max_bytes if isinstance(cfg, FileSecretProvider) else DEFAULT_MAX_OUTPUT_BYTES
        content = p.read_bytes()
        if len(content) > max_bytes:
            logger.warning("Secret file exceeds max bytes: %s", file_path)
            return None
        text = content.decode("utf-8").strip()

        if isinstance(cfg, FileSecretProvider) and cfg.mode == "json":
            import json

            data = json.loads(text)
            parts = ref.id.strip("/").split("/")
            for part in parts:
                if isinstance(data, dict):
                    data = data.get(part)
                else:
                    return None
            return str(data) if data is not None else None

        return text or None
    except Exception:
        logger.warning("Failed to read secret file: %s", file_path)
        return None


def _resolve_exec(ref: SecretRef, cfg: SecretProviderConfig | None) -> str | None:
    cmd = ref.id
    args: list[str] = []
    timeout = DEFAULT_EXEC_TIMEOUT_S
    exec_env: dict[str, str] | None = None

    if cfg and isinstance(cfg, ExecSecretProvider):
        cmd = cfg.command or ref.id
        args = list(cfg.args)
        timeout = cfg.timeout_ms / 1000.0
        if cfg.env:
            exec_env = {**os.environ, **cfg.env}

    try:
        result = subprocess.run(
            [cmd, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=exec_env,
        )
        if result.returncode != 0:
            logger.warning("Secret exec failed (exit %d): %s", result.returncode, cmd)
            return None
        return result.stdout.strip() or None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.warning("Secret exec error: %s — %s", cmd, exc)
        return None
