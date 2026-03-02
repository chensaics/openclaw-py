"""Environment variable substitution — ``${VAR}`` syntax parsing and replacement.

Ported from ``src/config/env-substitution.ts``.

Provides:
- ``${VAR}`` syntax parsing and substitution
- ``$${VAR}`` literal escape (outputs ``${VAR}`` verbatim)
- ``MissingEnvVarError`` for required variables
- Uppercase-only restriction for security
- Recursive substitution prevention
- Default values via ``${VAR:-default}``
"""

from __future__ import annotations

import os
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ${VAR} or ${VAR:-default}
_ENV_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-(.*?))?\}")
# Escaped literal: $${...}
_ESCAPED_PATTERN = re.compile(r"\$\$\{([^}]*)\}")

MAX_SUBSTITUTION_DEPTH = 10


class MissingEnvVarError(Exception):
    """Raised when a required environment variable is not set."""

    def __init__(self, var_name: str, context: str = "") -> None:
        self.var_name = var_name
        self.context = context
        msg = f"Environment variable '{var_name}' is not set"
        if context:
            msg += f" (in {context})"
        super().__init__(msg)


def _is_valid_var_name(name: str) -> bool:
    """Check if a variable name is valid (uppercase + digits + underscore only)."""
    return bool(re.match(r"^[A-Z_][A-Z0-9_]*$", name))


def substitute_env(
    text: str,
    *,
    env: dict[str, str] | None = None,
    strict: bool = False,
    context: str = "",
) -> str:
    """Substitute ``${VAR}`` patterns in text with environment values.

    Args:
        text: Input text with ``${VAR}`` patterns.
        env: Environment dict (defaults to ``os.environ``).
        strict: If True, raise ``MissingEnvVarError`` for undefined vars.
        context: Context string for error messages.

    Returns:
        Text with substitutions applied.

    ``$${VAR}`` is treated as a literal ``${VAR}`` (escape hatch).
    ``${VAR:-default}`` uses ``default`` if VAR is not set.
    """
    if "${" not in text:
        return text

    source = env if env is not None else dict(os.environ)

    # First, protect escaped patterns
    escaped_slots: list[str] = []

    def _protect_escaped(m: re.Match[str]) -> str:
        slot = f"\x00ESC{len(escaped_slots)}\x00"
        escaped_slots.append(m.group(1))
        return slot

    result = _ESCAPED_PATTERN.sub(_protect_escaped, text)

    # Substitute ${VAR} and ${VAR:-default}
    depth = 0

    def _replace(m: re.Match[str]) -> str:
        var_name = m.group(1)
        default = m.group(2)

        if not _is_valid_var_name(var_name):
            return m.group(0)  # Leave invalid names as-is

        value = source.get(var_name)
        if value is None:
            if default is not None:
                return default
            if strict:
                raise MissingEnvVarError(var_name, context)
            return m.group(0)  # Leave unresolved
        return value

    while _ENV_PATTERN.search(result) and depth < MAX_SUBSTITUTION_DEPTH:
        result = _ENV_PATTERN.sub(_replace, result)
        depth += 1

    # Restore escaped patterns
    for i, content in enumerate(escaped_slots):
        result = result.replace(f"\x00ESC{i}\x00", f"${{{content}}}")

    return result


def substitute_env_recursive(
    data: Any,
    *,
    env: dict[str, str] | None = None,
    strict: bool = False,
    context: str = "",
) -> Any:
    """Recursively substitute env vars in a nested dict/list structure."""
    if isinstance(data, str):
        return substitute_env(data, env=env, strict=strict, context=context)
    if isinstance(data, dict):
        return {
            k: substitute_env_recursive(v, env=env, strict=strict, context=f"{context}.{k}")
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [
            substitute_env_recursive(v, env=env, strict=strict, context=f"{context}[{i}]")
            for i, v in enumerate(data)
        ]
    return data


def list_env_refs(text: str) -> list[str]:
    """List all environment variable references in text."""
    refs: list[str] = []
    for m in _ENV_PATTERN.finditer(text):
        name = m.group(1)
        if name not in refs:
            refs.append(name)
    return refs


def validate_env_refs(
    text: str,
    *,
    env: dict[str, str] | None = None,
) -> list[str]:
    """Validate that all referenced env vars exist. Returns list of missing var names."""
    source = env if env is not None else dict(os.environ)
    missing: list[str] = []
    for name in list_env_refs(text):
        if name not in source:
            missing.append(name)
    return missing
