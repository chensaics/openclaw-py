"""Session command handlers — /session, /stop, /compact.

Ported from ``src/auto-reply/reply/commands-session.ts``.
"""

from __future__ import annotations

from typing import Any

from .commands_registry import CommandContext, CommandRegistry, CommandResult


async def handle_session(ctx: CommandContext) -> CommandResult:
    """Handle /session subcommands: new, reset, list, idle, max-age."""
    args = ctx.command.args
    action = args[0].lower() if args else "list"

    if action == "new":
        return CommandResult(text="New session started.", metadata={"action": "session_new"})

    if action == "reset":
        return CommandResult(text="Session reset.", metadata={"action": "session_reset"})

    if action == "list":
        sessions: list[dict[str, Any]] = ctx.metadata.get("sessions", [])
        if not sessions:
            return CommandResult(text="No active sessions.")
        lines = ["**Sessions**\n"]
        for s in sessions[:10]:
            sid = s.get("id", "?")
            model = s.get("model", "?")
            turns = s.get("turns", 0)
            lines.append(f"- `{sid}` — {model} ({turns} turns)")
        return CommandResult(text="\n".join(lines))

    if action == "idle":
        hours = args[1] if len(args) > 1 else "24"
        return CommandResult(
            text=f"Session idle timeout set to {hours}h.",
            metadata={"action": "set_idle", "hours": hours},
        )

    if action == "max-age":
        hours = args[1] if len(args) > 1 else "168"
        return CommandResult(
            text=f"Session max age set to {hours}h.",
            metadata={"action": "set_max_age", "hours": hours},
        )

    return CommandResult(text=f"Unknown session action: {action}", success=False)


async def handle_stop(ctx: CommandContext) -> CommandResult:
    """Handle /stop — abort current generation."""
    return CommandResult(
        text="Generation stopped.",
        stop_processing=True,
        metadata={"action": "stop"},
    )


async def handle_compact(ctx: CommandContext) -> CommandResult:
    """Handle /compact — manually compact session history."""
    info: dict[str, Any] = ctx.metadata.get("compact_info", {})
    before = info.get("entries_before", "?")
    after = info.get("entries_after", "?")
    return CommandResult(
        text=f"Session compacted: {before} → {after} entries.",
        metadata={"action": "compact"},
    )


def register_session_commands(registry: CommandRegistry) -> None:
    """Register session-related commands."""
    handlers = {
        "session": handle_session,
        "stop": handle_stop,
        "compact": handle_compact,
    }
    for name, handler in handlers.items():
        defn = registry.get_command(name)
        if defn:
            registry.register(defn, handler)
