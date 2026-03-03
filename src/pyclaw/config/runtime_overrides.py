"""Runtime configuration overrides — group policies, channel capabilities, plugin auto-enable.

Ported from ``src/config/runtime-overrides*.ts``.

Provides:
- Runtime override layer on top of static config
- Group-level policy overrides
- Channel capability overrides
- Plugin auto-enable rules
- Config snapshot with sensitive field redaction
"""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass, field
from typing import Any, cast

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = re.compile(
    r"(password|secret|token|api_key|apikey|private_key|access_key|credentials)",
    re.IGNORECASE,
)
_REDACTED = "***REDACTED***"


@dataclass
class GroupPolicy:
    """Policy overrides for a specific group/chat."""
    group_id: str
    model: str = ""
    think_level: str = ""
    max_tokens: int = 0
    tools_allowed: list[str] = field(default_factory=list)
    tools_blocked: list[str] = field(default_factory=list)
    custom: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelCapabilityOverride:
    """Override channel capabilities at runtime."""
    channel_id: str
    streaming_enabled: bool | None = None
    reactions_enabled: bool | None = None
    max_message_length: int | None = None
    media_enabled: bool | None = None


@dataclass
class PluginAutoEnable:
    """Rule for auto-enabling a plugin."""
    plugin_name: str
    condition: str = "always"     # "always" | "if_configured" | "if_channel"
    channel_types: list[str] = field(default_factory=list)


class RuntimeOverrides:
    """Manage runtime configuration overrides."""

    def __init__(self) -> None:
        self._group_policies: dict[str, GroupPolicy] = {}
        self._channel_overrides: dict[str, ChannelCapabilityOverride] = {}
        self._plugin_rules: list[PluginAutoEnable] = []
        self._overrides: dict[str, Any] = {}

    # -- Group policies --

    def set_group_policy(self, policy: GroupPolicy) -> None:
        self._group_policies[policy.group_id] = policy

    def get_group_policy(self, group_id: str) -> GroupPolicy | None:
        return self._group_policies.get(group_id)

    def remove_group_policy(self, group_id: str) -> bool:
        return self._group_policies.pop(group_id, None) is not None

    def list_group_policies(self) -> list[GroupPolicy]:
        return list(self._group_policies.values())

    # -- Channel overrides --

    def set_channel_override(self, override: ChannelCapabilityOverride) -> None:
        self._channel_overrides[override.channel_id] = override

    def get_channel_override(self, channel_id: str) -> ChannelCapabilityOverride | None:
        return self._channel_overrides.get(channel_id)

    # -- Plugin auto-enable --

    def add_plugin_rule(self, rule: PluginAutoEnable) -> None:
        self._plugin_rules.append(rule)

    def get_auto_enable_plugins(self, *, channel_type: str = "") -> list[str]:
        """Get list of plugins that should be auto-enabled."""
        plugins: list[str] = []
        for rule in self._plugin_rules:
            if rule.condition == "always":
                plugins.append(rule.plugin_name)
            elif rule.condition == "if_channel" and channel_type:
                if channel_type in rule.channel_types:
                    plugins.append(rule.plugin_name)
        return plugins

    # -- Generic overrides --

    def set(self, key: str, value: Any) -> None:
        self._overrides[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._overrides.get(key, default)

    def remove(self, key: str) -> bool:
        return self._overrides.pop(key, None) is not None

    # -- Merge with static config --

    def apply_to_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Apply runtime overrides to a static config dict."""
        result = copy.deepcopy(config)

        for key, value in self._overrides.items():
            _set_nested(result, key, value)

        return result


def _set_nested(data: dict[str, Any], key: str, value: Any) -> None:
    """Set a value in a nested dict using dot-notation key."""
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def redact_config(config: dict[str, Any]) -> dict[str, Any]:
    """Create a copy of config with sensitive values redacted."""
    return cast(dict[str, Any], _redact_recursive(copy.deepcopy(config)))


def _redact_recursive(data: Any) -> Any:
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if _SENSITIVE_KEYS.search(key) and isinstance(value, str) and value:
                result[key] = _REDACTED
            else:
                result[key] = _redact_recursive(value)
        return result
    if isinstance(data, list):
        return [_redact_recursive(v) for v in data]
    return data


def create_config_snapshot(
    config: dict[str, Any],
    overrides: RuntimeOverrides,
    *,
    redact: bool = True,
) -> dict[str, Any]:
    """Create a config snapshot with overrides applied and optionally redacted."""
    merged = overrides.apply_to_config(config)
    if redact:
        merged = redact_config(merged)
    return merged
