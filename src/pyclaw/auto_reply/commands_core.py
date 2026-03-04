"""Core command handlers — /help, /status, /whoami, /context, /usage, /export.

Ported from ``src/auto-reply/reply/commands-info.ts``.
"""

from __future__ import annotations

from typing import Any

from .commands_registry import (
    CommandContext,
    CommandRegistry,
    CommandResult,
)


async def handle_help(ctx: CommandContext) -> CommandResult:
    """Show available commands grouped by category."""
    registry: CommandRegistry | None = ctx.metadata.get("registry")
    if not registry:
        return CommandResult(text="Command registry not available.")

    commands = registry.list_commands()
    categories: dict[str, list[str]] = {}
    for cmd in commands:
        cat = cmd.category or "general"
        line = f"  `/{cmd.name}`"
        if cmd.aliases:
            aliases = ", ".join(f"/{a}" for a in cmd.aliases)
            line += f" ({aliases})"
        line += f" — {cmd.description}"
        categories.setdefault(cat, []).append(line)

    parts = ["**Available Commands**\n"]
    for cat in sorted(categories):
        parts.append(f"**{cat.title()}**")
        parts.extend(categories[cat])
        parts.append("")

    return CommandResult(text="\n".join(parts))


async def handle_status(ctx: CommandContext) -> CommandResult:
    """Show current session and channel status."""
    info: dict[str, Any] = ctx.metadata.get("status_info", {})

    lines = ["**Status**\n"]
    lines.append(f"- Channel: `{ctx.channel_id or 'unknown'}`")
    lines.append(f"- Session: `{ctx.session_id or 'none'}`")
    lines.append(f"- Sender: `{ctx.sender_id or 'unknown'}`")

    if model := info.get("model"):
        lines.append(f"- Model: `{model}`")
    if uptime := info.get("uptime"):
        lines.append(f"- Uptime: {uptime}")

    return CommandResult(text="\n".join(lines))


async def handle_whoami(ctx: CommandContext) -> CommandResult:
    """Show identity information."""
    lines = ["**Identity**\n"]
    lines.append(f"- Sender ID: `{ctx.sender_id}`")
    lines.append(f"- Channel: `{ctx.channel_id}`")
    lines.append(f"- Type: `{ctx.channel_type}`")
    lines.append(f"- Owner: {'yes' if ctx.is_owner else 'no'}")

    if account := ctx.metadata.get("account_id"):
        lines.append(f"- Account: `{account}`")

    return CommandResult(text="\n".join(lines))


async def handle_context(ctx: CommandContext) -> CommandResult:
    """Show context information (model, tokens, session)."""
    info: dict[str, Any] = ctx.metadata.get("context_info", {})

    lines = ["**Context**\n"]
    if model := info.get("model"):
        lines.append(f"- Model: `{model}`")
    if tokens := info.get("token_count"):
        lines.append(f"- Tokens: {tokens:,}")
    if max_tokens := info.get("max_tokens"):
        lines.append(f"- Max tokens: {max_tokens:,}")
    if entries := info.get("entry_count"):
        lines.append(f"- Entries: {entries}")
    if tools := info.get("tool_count"):
        lines.append(f"- Tools: {tools}")
    if skills := info.get("skill_count"):
        lines.append(f"- Skills: {skills}")

    if not info:
        lines.append("No context information available.")

    return CommandResult(text="\n".join(lines))


async def handle_usage(ctx: CommandContext) -> CommandResult:
    """Show usage statistics or set usage footer mode."""
    mode = (ctx.command.args[0].lower() if ctx.command.args else "").strip()
    if mode in {"full", "tokens", "off"}:
        return CommandResult(
            text=f"Usage footer mode set to `{mode}`.",
            metadata={"action": "set_usage_mode", "mode": mode},
        )

    info: dict[str, Any] = dict(ctx.metadata.get("usage_info", {}))
    if not info and ctx.session_id:
        try:
            from pyclaw.infra.session_cost import summarize_session_usage

            usage = summarize_session_usage(ctx.session_id)
            info = {
                "session_tokens": usage.get("session_tokens", 0),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "estimated_cost_value": usage.get("estimated_cost_value", 0.0),
                "turn_count": usage.get("calls", 0),
                "auth_type": "api_key",
            }
        except Exception:
            info = {}

    lines = ["**Usage**\n"]
    session_tokens = int(info.get("session_tokens", 0) or 0)
    input_tokens = int(info.get("input_tokens", 0) or 0)
    output_tokens = int(info.get("output_tokens", 0) or 0)
    total_tokens = int(info.get("total_tokens", 0) or (input_tokens + output_tokens))
    turns = int(info.get("turn_count", 0) or 0)

    if session_tokens:
        lines.append(f"- Session tokens: {session_tokens:,}")
    if input_tokens or output_tokens:
        lines.append(f"- Input/Output: {input_tokens:,} / {output_tokens:,}")
    if total_tokens:
        lines.append(f"- Total tokens: {total_tokens:,}")
    if turns:
        lines.append(f"- Turns: {turns}")

    # Cost display gate: hide dollar cost for token-only mode or non API-key auth.
    auth_type = str(info.get("auth_type", "api_key") or "api_key")
    show_cost = auth_type == "api_key"
    if show_cost:
        if "estimated_cost" in info:
            lines.append(f"- Estimated cost: {info['estimated_cost']}")
        elif "estimated_cost_value" in info:
            lines.append(f"- Estimated cost: ${float(info['estimated_cost_value']):.4f}")

    if len(lines) == 1:
        lines.append("No usage data available.")

    return CommandResult(text="\n".join(lines))


async def handle_export(ctx: CommandContext) -> CommandResult:
    """Export session (delegates to export_html module)."""
    return CommandResult(text="Session export initiated. Check your downloads.")


def register_core_commands(registry: CommandRegistry) -> None:
    """Register core info commands on a registry."""
    handlers = {
        "help": handle_help,
        "status": handle_status,
        "whoami": handle_whoami,
        "context": handle_context,
        "usage": handle_usage,
        "export": handle_export,
    }
    for name, handler in handlers.items():
        defn = registry.get_command(name)
        if defn:
            registry.register(defn, handler)
