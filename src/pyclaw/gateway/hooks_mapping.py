"""Hooks mapping — presets, conversion rules, template replacement.

Ported from ``src/gateway/hooks-mapping.ts``.

Provides:
- Hook preset definitions (gmail, etc.)
- Hook mapping resolution from config
- Template variable replacement in hook configs
- Hook mapping application to runtime config
"""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HookPreset:
    """A predefined hook configuration template."""

    name: str
    description: str = ""
    hook_type: str = ""
    config_template: dict[str, Any] = field(default_factory=dict)
    required_vars: list[str] = field(default_factory=list)
    optional_vars: list[str] = field(default_factory=list)


# Built-in presets
GMAIL_PRESET = HookPreset(
    name="gmail",
    description="Gmail new email watcher",
    hook_type="gmail-watcher",
    config_template={
        "type": "gmail-watcher",
        "credentials_path": "${GMAIL_CREDENTIALS_PATH}",
        "check_interval_s": 60,
        "label": "${GMAIL_LABEL:-INBOX}",
        "max_results": 5,
    },
    required_vars=["GMAIL_CREDENTIALS_PATH"],
    optional_vars=["GMAIL_LABEL"],
)

WEBHOOK_PRESET = HookPreset(
    name="webhook",
    description="Generic webhook receiver",
    hook_type="webhook",
    config_template={
        "type": "webhook",
        "path": "${WEBHOOK_PATH:-/hooks/incoming}",
        "secret": "${WEBHOOK_SECRET}",
    },
    required_vars=["WEBHOOK_SECRET"],
    optional_vars=["WEBHOOK_PATH"],
)

BUILTIN_PRESETS: dict[str, HookPreset] = {
    "gmail": GMAIL_PRESET,
    "webhook": WEBHOOK_PRESET,
}


@dataclass
class HookMapping:
    """A resolved hook mapping ready for application."""

    hook_id: str
    hook_type: str
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    from_preset: str = ""


@dataclass
class HookMappingResult:
    """Result of resolving hook mappings."""

    mappings: list[HookMapping] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_TEMPLATE_RE = re.compile(r"\$\{(\w+)(?::-(.*?))?\}")


def substitute_template(value: str, variables: dict[str, str]) -> str:
    """Replace ${VAR} and ${VAR:-default} in a string."""

    def replacer(m: re.Match[str]) -> str:
        var_name = m.group(1)
        default = m.group(2)
        if var_name in variables:
            return variables[var_name]
        if default is not None:
            return default
        return m.group(0)

    return _TEMPLATE_RE.sub(replacer, value)


def substitute_config(config: dict[str, Any], variables: dict[str, str]) -> dict[str, Any]:
    """Recursively substitute template variables in a config dict."""
    result: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, str):
            result[key] = substitute_template(value, variables)
        elif isinstance(value, dict):
            result[key] = substitute_config(value, variables)
        elif isinstance(value, list):
            result[key] = [substitute_template(v, variables) if isinstance(v, str) else v for v in value]
        else:
            result[key] = value
    return result


def resolve_hook_mappings(
    hooks_config: list[dict[str, Any]],
    variables: dict[str, str] | None = None,
) -> HookMappingResult:
    """Resolve hook mappings from config entries."""
    result = HookMappingResult()
    variables = variables or {}

    for i, entry in enumerate(hooks_config):
        hook_id = entry.get("id", f"hook-{i}")

        # Preset-based
        preset_name = entry.get("preset")
        if preset_name:
            preset = BUILTIN_PRESETS.get(preset_name)
            if not preset:
                result.errors.append(f"Unknown preset '{preset_name}' for hook '{hook_id}'")
                continue

            missing = [v for v in preset.required_vars if v not in variables]
            if missing:
                result.warnings.append(f"Hook '{hook_id}': missing variables {missing} for preset '{preset_name}'")

            config = substitute_config(copy.deepcopy(preset.config_template), variables)
            # Allow config overrides
            for k, v in entry.items():
                if k not in ("id", "preset", "enabled"):
                    config[k] = v

            result.mappings.append(
                HookMapping(
                    hook_id=hook_id,
                    hook_type=preset.hook_type,
                    config=config,
                    enabled=entry.get("enabled", True),
                    from_preset=preset_name,
                )
            )
        else:
            hook_type = entry.get("type", "")
            if not hook_type:
                result.errors.append(f"Hook '{hook_id}': missing 'type' or 'preset'")
                continue

            config = {k: v for k, v in entry.items() if k not in ("id", "enabled")}
            config = substitute_config(config, variables)

            result.mappings.append(
                HookMapping(
                    hook_id=hook_id,
                    hook_type=hook_type,
                    config=config,
                    enabled=entry.get("enabled", True),
                )
            )

    return result


def apply_hook_mappings(
    runtime_config: dict[str, Any],
    mappings: list[HookMapping],
) -> dict[str, Any]:
    """Apply resolved hook mappings to a runtime config dict."""
    config = copy.deepcopy(runtime_config)
    hooks = config.setdefault("hooks", [])

    for mapping in mappings:
        if not mapping.enabled:
            continue

        hook_entry = {
            "id": mapping.hook_id,
            "type": mapping.hook_type,
            **mapping.config,
        }

        # Replace if same ID exists, otherwise append
        replaced = False
        for i, existing in enumerate(hooks):
            if existing.get("id") == mapping.hook_id:
                hooks[i] = hook_entry
                replaced = True
                break
        if not replaced:
            hooks.append(hook_entry)

    return config
