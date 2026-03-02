"""Slash command registry — command definitions, parsing, and dispatch.

Ported from ``src/auto-reply/commands-registry.ts`` in the TypeScript codebase.

Provides:
- Command definition (name, aliases, args schema, scope, help text)
- Command parsing from inbound messages (prefix matching)
- 20+ built-in command registrations
- Command dispatch to handlers
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class CommandScope(str, Enum):
    """Where a command can be invoked."""
    ALL = "all"
    DM = "dm"
    GROUP = "group"
    OWNER = "owner"


@dataclass
class CommandArg:
    """A single argument for a command."""
    name: str
    required: bool = False
    description: str = ""
    choices: list[str] = field(default_factory=list)


@dataclass
class CommandDef:
    """A slash command definition."""
    name: str
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    args: list[CommandArg] = field(default_factory=list)
    scope: CommandScope = CommandScope.ALL
    hidden: bool = False
    category: str = "general"

    @property
    def all_triggers(self) -> list[str]:
        return [self.name] + self.aliases


@dataclass
class ParsedCommand:
    """Result of parsing a slash command from text."""
    name: str
    args: list[str]
    raw_args: str
    definition: CommandDef | None = None


CommandHandler = Callable[["CommandContext"], Coroutine[Any, Any, "CommandResult"]]


@dataclass
class CommandContext:
    """Context passed to a command handler."""
    command: ParsedCommand
    sender_id: str = ""
    channel_id: str = ""
    channel_type: str = ""  # "dm" | "group"
    session_id: str = ""
    is_owner: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandResult:
    """Result from a command handler."""
    text: str = ""
    success: bool = True
    silent: bool = False        # Don't send reply
    stop_processing: bool = True  # Don't continue to agent
    metadata: dict[str, Any] = field(default_factory=dict)


_COMMAND_PREFIX = "/"
_COMMAND_PATTERN = re.compile(r"^/([a-zA-Z][\w-]*)\s*(.*)", re.DOTALL)


class CommandRegistry:
    """Registry for slash commands with parsing and dispatch."""

    def __init__(self) -> None:
        self._commands: dict[str, CommandDef] = {}
        self._handlers: dict[str, CommandHandler] = {}
        self._trigger_map: dict[str, str] = {}  # trigger -> canonical name

    def register(
        self,
        definition: CommandDef,
        handler: CommandHandler,
    ) -> None:
        """Register a command with its handler."""
        name = definition.name
        self._commands[name] = definition
        self._handlers[name] = handler

        for trigger in definition.all_triggers:
            trigger_lower = trigger.lower()
            if trigger_lower in self._trigger_map:
                logger.warning(
                    "Command trigger '%s' already registered for '%s', overwriting with '%s'",
                    trigger, self._trigger_map[trigger_lower], name,
                )
            self._trigger_map[trigger_lower] = name

    def unregister(self, name: str) -> bool:
        defn = self._commands.pop(name, None)
        if not defn:
            return False
        self._handlers.pop(name, None)
        for trigger in defn.all_triggers:
            self._trigger_map.pop(trigger.lower(), None)
        return True

    def parse(self, text: str) -> ParsedCommand | None:
        """Parse a slash command from message text.

        Returns None if text is not a command.
        Supports prefix matching: ``/h`` matches ``/help``.
        """
        text = text.strip()
        if not text.startswith(_COMMAND_PREFIX):
            return None

        match = _COMMAND_PATTERN.match(text)
        if not match:
            return None

        trigger = match.group(1).lower()
        raw_args = match.group(2).strip()

        # Exact match first
        if trigger in self._trigger_map:
            canonical = self._trigger_map[trigger]
            args = raw_args.split() if raw_args else []
            return ParsedCommand(
                name=canonical,
                args=args,
                raw_args=raw_args,
                definition=self._commands.get(canonical),
            )

        # Prefix match
        candidates = [
            t for t in self._trigger_map
            if t.startswith(trigger) and len(trigger) >= 1
        ]
        if len(candidates) == 1:
            canonical = self._trigger_map[candidates[0]]
            args = raw_args.split() if raw_args else []
            return ParsedCommand(
                name=canonical,
                args=args,
                raw_args=raw_args,
                definition=self._commands.get(canonical),
            )

        return None

    def is_command(self, text: str) -> bool:
        return self.parse(text.strip()) is not None

    async def dispatch(self, context: CommandContext) -> CommandResult | None:
        """Dispatch a parsed command to its handler."""
        name = context.command.name
        defn = self._commands.get(name)
        if not defn:
            return CommandResult(text=f"Unknown command: /{name}", success=False)

        # Scope check
        if defn.scope == CommandScope.OWNER and not context.is_owner:
            return CommandResult(text="This command is owner-only.", success=False)
        if defn.scope == CommandScope.DM and context.channel_type == "group":
            return CommandResult(text="This command is only available in DMs.", success=False)
        if defn.scope == CommandScope.GROUP and context.channel_type == "dm":
            return CommandResult(text="This command is only available in groups.", success=False)

        handler = self._handlers.get(name)
        if not handler:
            return CommandResult(text=f"No handler for /{name}", success=False)

        return await handler(context)

    def get_command(self, name: str) -> CommandDef | None:
        return self._commands.get(name)

    def list_commands(
        self,
        *,
        include_hidden: bool = False,
        category: str | None = None,
    ) -> list[CommandDef]:
        commands = list(self._commands.values())
        if not include_hidden:
            commands = [c for c in commands if not c.hidden]
        if category:
            commands = [c for c in commands if c.category == category]
        return sorted(commands, key=lambda c: c.name)

    @property
    def command_count(self) -> int:
        return len(self._commands)


# ---------------------------------------------------------------------------
# Built-in command definitions
# ---------------------------------------------------------------------------

BUILTIN_COMMANDS: list[CommandDef] = [
    CommandDef(name="help", aliases=["h", "?"], description="Show available commands", category="info"),
    CommandDef(name="status", aliases=["st"], description="Show current status", category="info"),
    CommandDef(name="whoami", description="Show identity information", category="info"),
    CommandDef(name="context", aliases=["ctx"], description="Show context information", category="info"),
    CommandDef(
        name="usage",
        description="Show usage / set usage footer mode",
        args=[CommandArg(name="mode", choices=["full", "tokens", "off"])],
        category="info",
    ),
    CommandDef(name="export", description="Export session as HTML", category="session"),
    CommandDef(
        name="session",
        aliases=["s"],
        description="Session management",
        args=[CommandArg(name="action", choices=["new", "reset", "list", "idle", "max-age"])],
        category="session",
    ),
    CommandDef(name="stop", description="Stop current generation", category="session"),
    CommandDef(name="compact", description="Compact session history", category="session"),
    CommandDef(
        name="model",
        aliases=["m"],
        description="Switch model",
        args=[CommandArg(name="model_name", description="Model to switch to")],
        category="model",
    ),
    CommandDef(
        name="think",
        aliases=["t"],
        description="Set thinking depth",
        args=[CommandArg(name="level", choices=["low", "medium", "high"])],
        category="model",
    ),
    CommandDef(name="debug", description="Show debug configuration", category="model", hidden=True),
    CommandDef(name="tts", description="Text-to-speech", category="tools"),
    CommandDef(name="approve", description="Approve pending execution", category="tools"),
    CommandDef(name="allowlist", aliases=["allow"], description="Manage allowlist", category="admin", scope=CommandScope.OWNER),
    CommandDef(name="send", description="Send message to channel", category="messaging"),
    CommandDef(name="bash", description="Execute shell command", category="tools", hidden=True),
    CommandDef(name="plugin", description="Plugin management", category="admin", scope=CommandScope.OWNER),
]


def create_default_registry() -> CommandRegistry:
    """Create a registry with all built-in command definitions (no handlers)."""
    registry = CommandRegistry()
    for cmd in BUILTIN_COMMANDS:
        async def _placeholder(ctx: CommandContext) -> CommandResult:
            return CommandResult(text=f"/{ctx.command.name}: not yet implemented")
        registry.register(cmd, _placeholder)
    return registry
