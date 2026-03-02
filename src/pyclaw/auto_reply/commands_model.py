"""Model command handlers — /model, /think, /debug.

Ported from ``src/auto-reply/reply/commands-models.ts``.
"""

from __future__ import annotations

from typing import Any

from .commands_registry import CommandContext, CommandRegistry, CommandResult


THINK_LEVELS = {"low", "medium", "high"}


async def handle_model(ctx: CommandContext) -> CommandResult:
    """Handle /model — switch or show current model."""
    args = ctx.command.args

    if not args:
        current = ctx.metadata.get("current_model", "unknown")
        available: list[str] = ctx.metadata.get("available_models", [])
        lines = [f"**Current model:** `{current}`"]
        if available:
            lines.append("\n**Available:**")
            for m in available[:15]:
                marker = " (current)" if m == current else ""
                lines.append(f"  - `{m}`{marker}")
        return CommandResult(text="\n".join(lines))

    target = args[0]
    available = ctx.metadata.get("available_models", [])
    if available and target not in available:
        # Prefix match
        matches = [m for m in available if m.startswith(target)]
        if len(matches) == 1:
            target = matches[0]
        elif len(matches) > 1:
            suggestions = ", ".join(f"`{m}`" for m in matches[:5])
            return CommandResult(
                text=f"Ambiguous model name. Did you mean: {suggestions}?",
                success=False,
            )

    return CommandResult(
        text=f"Model switched to `{target}`.",
        metadata={"action": "switch_model", "model": target},
    )


async def handle_think(ctx: CommandContext) -> CommandResult:
    """Handle /think — set thinking depth (low/medium/high)."""
    args = ctx.command.args

    if not args:
        current = ctx.metadata.get("think_level", "medium")
        return CommandResult(text=f"**Thinking level:** `{current}`\nOptions: low, medium, high")

    level = args[0].lower()
    if level not in THINK_LEVELS:
        return CommandResult(
            text=f"Invalid level: `{level}`. Use: low, medium, high.",
            success=False,
        )

    return CommandResult(
        text=f"Thinking level set to `{level}`.",
        metadata={"action": "set_think", "level": level},
    )


async def handle_debug(ctx: CommandContext) -> CommandResult:
    """Handle /debug — show debug configuration."""
    info: dict[str, Any] = ctx.metadata.get("debug_info", {})

    lines = ["**Debug Info**\n"]
    for key, value in sorted(info.items()):
        lines.append(f"- {key}: `{value}`")

    if not info:
        lines.append("No debug information available.")

    return CommandResult(text="\n".join(lines))


def register_model_commands(registry: CommandRegistry) -> None:
    """Register model-related commands."""
    handlers = {
        "model": handle_model,
        "think": handle_think,
        "debug": handle_debug,
    }
    for name, handler in handlers.items():
        defn = registry.get_command(name)
        if defn:
            registry.register(defn, handler)
