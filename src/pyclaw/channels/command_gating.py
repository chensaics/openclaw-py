"""Command gating — per-channel command permission control.

Ported from ``src/channels/command-gating.ts``.

Controls which slash commands (``/model``, ``/think``, ``/queue``, etc.)
are available in each channel, with per-channel and per-role overrides.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CommandPermission(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    OWNER_ONLY = "owner_only"


# Built-in commands with default permissions
BUILTIN_COMMANDS: dict[str, CommandPermission] = {
    "/help": CommandPermission.ALLOW,
    "/model": CommandPermission.OWNER_ONLY,
    "/think": CommandPermission.ALLOW,
    "/queue": CommandPermission.OWNER_ONLY,
    "/clear": CommandPermission.OWNER_ONLY,
    "/reset": CommandPermission.OWNER_ONLY,
    "/status": CommandPermission.OWNER_ONLY,
    "/config": CommandPermission.OWNER_ONLY,
    "/bind": CommandPermission.OWNER_ONLY,
    "/unbind": CommandPermission.OWNER_ONLY,
    "/agent": CommandPermission.OWNER_ONLY,
    "/cancel": CommandPermission.ALLOW,
    "/retry": CommandPermission.ALLOW,
    "/undo": CommandPermission.ALLOW,
    "/compact": CommandPermission.OWNER_ONLY,
    "/debug": CommandPermission.OWNER_ONLY,
}


@dataclass
class CommandGatingConfig:
    """Per-channel command gating configuration."""

    channel_id: str
    # Per-command overrides (command → permission)
    overrides: dict[str, CommandPermission] = field(default_factory=dict)
    # Deny all commands not explicitly allowed
    deny_unlisted: bool = False
    # Owner IDs for this channel
    owner_ids: set[str] = field(default_factory=set)
    # Disable all commands
    disabled: bool = False


@dataclass
class CommandGateResult:
    """Result of a command gate check."""

    allowed: bool
    command: str
    reason: str = ""


class CommandGatingManager:
    """Manages command permissions across channels."""

    def __init__(self) -> None:
        self._configs: dict[str, CommandGatingConfig] = {}
        self._global_overrides: dict[str, CommandPermission] = {}

    def register_channel(self, config: CommandGatingConfig) -> None:
        self._configs[config.channel_id] = config

    def unregister_channel(self, channel_id: str) -> None:
        self._configs.pop(channel_id, None)

    def set_global_override(self, command: str, permission: CommandPermission) -> None:
        """Set a global command permission override (applies to all channels)."""
        self._global_overrides[command] = permission

    def check(
        self,
        channel_id: str,
        command: str,
        sender_id: str,
    ) -> CommandGateResult:
        """Check if a command is allowed for a sender on a channel.

        Resolution order:
        1. Channel disabled → deny all
        2. Channel per-command override
        3. Global override
        4. Built-in default
        5. deny_unlisted fallback
        """
        cmd = command.lower().strip()
        if not cmd.startswith("/"):
            cmd = f"/{cmd}"

        config = self._configs.get(channel_id)

        # No config — use defaults
        if config is None:
            return self._check_default(cmd, sender_id, owner_ids=set())

        # Channel disabled
        if config.disabled:
            return CommandGateResult(
                allowed=False,
                command=cmd,
                reason="commands disabled for channel",
            )

        is_owner = sender_id in config.owner_ids

        # Channel override
        if cmd in config.overrides:
            perm = config.overrides[cmd]
            return self._resolve_permission(cmd, perm, is_owner)

        # Global override
        if cmd in self._global_overrides:
            perm = self._global_overrides[cmd]
            return self._resolve_permission(cmd, perm, is_owner)

        # Built-in default
        if cmd in BUILTIN_COMMANDS:
            perm = BUILTIN_COMMANDS[cmd]
            return self._resolve_permission(cmd, perm, is_owner)

        # Unlisted command
        if config.deny_unlisted:
            return CommandGateResult(
                allowed=False,
                command=cmd,
                reason="unlisted command denied",
            )

        return CommandGateResult(allowed=True, command=cmd)

    def get_available_commands(
        self,
        channel_id: str,
        sender_id: str,
    ) -> list[str]:
        """Get all commands available to a sender on a channel."""
        available: list[str] = []

        all_commands = set(BUILTIN_COMMANDS.keys())
        config = self._configs.get(channel_id)
        if config:
            all_commands.update(config.overrides.keys())
        all_commands.update(self._global_overrides.keys())

        for cmd in sorted(all_commands):
            result = self.check(channel_id, cmd, sender_id)
            if result.allowed:
                available.append(cmd)

        return available

    def _check_default(
        self,
        command: str,
        sender_id: str,
        *,
        owner_ids: set[str],
    ) -> CommandGateResult:
        """Check against built-in defaults only."""
        is_owner = sender_id in owner_ids
        perm = BUILTIN_COMMANDS.get(command)

        if perm is None:
            return CommandGateResult(allowed=True, command=command)

        return self._resolve_permission(command, perm, is_owner)

    def _resolve_permission(
        self,
        command: str,
        permission: CommandPermission,
        is_owner: bool,
    ) -> CommandGateResult:
        """Resolve a permission enum to an allow/deny result."""
        if permission == CommandPermission.ALLOW:
            return CommandGateResult(allowed=True, command=command)

        if permission == CommandPermission.DENY:
            return CommandGateResult(allowed=False, command=command, reason="denied by policy")

        if permission == CommandPermission.OWNER_ONLY:
            if is_owner:
                return CommandGateResult(allowed=True, command=command, reason="owner")
            return CommandGateResult(
                allowed=False,
                command=command,
                reason="owner only",
            )

        return CommandGateResult(allowed=False, command=command, reason="unknown permission")
