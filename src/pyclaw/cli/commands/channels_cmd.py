"""CLI channels subcommands — list, status, add, remove."""

from __future__ import annotations

import json

import typer

from pyclaw.config.io import load_config, load_config_raw, save_config
from pyclaw.config.paths import resolve_config_path
from pyclaw.config.schema import PyClawConfig
from pyclaw.constants.runtime import DEFAULT_GATEWAY_BIND, DEFAULT_GATEWAY_PORT
from pyclaw.terminal.palette import PALETTE
from pyclaw.terminal.table import TableColumn, render_table


def channels_list() -> None:
    """List configured channels."""
    p = PALETTE
    config_path = resolve_config_path()

    if not config_path.exists():
        typer.echo(f"  {p.muted}No config found.{p.reset}")
        return

    try:
        cfg = load_config(config_path)
    except Exception as e:
        typer.echo(f"{p.error}Config error: {e}{p.reset}")
        return

    rows: list[dict[str, str]] = []

    # Check each channel type in config
    channel_checks = [
        ("telegram", cfg.telegram if hasattr(cfg, "telegram") else None),
        ("discord", cfg.discord if hasattr(cfg, "discord") else None),
        ("slack", cfg.slack if hasattr(cfg, "slack") else None),
        ("whatsapp", cfg.whatsapp if hasattr(cfg, "whatsapp") else None),
        ("signal", cfg.signal if hasattr(cfg, "signal") else None),
    ]

    for channel_id, channel_cfg in channel_checks:
        if channel_cfg:
            enabled = getattr(channel_cfg, "enabled", True) if channel_cfg else False
            rows.append({"channel": channel_id, "status": "enabled" if enabled else "disabled"})

    if not rows:
        typer.echo(f"  {p.muted}No channels configured.{p.reset}")
        return

    cols = [
        TableColumn(key="channel", header="Channel", min_width=10),
        TableColumn(key="status", header="Status", min_width=8),
    ]
    typer.echo(f"\n{p.info}Channels:{p.reset}")
    typer.echo(render_table(cols, rows))


def channels_status() -> None:
    """Show detailed channel status (requires running gateway)."""
    p = PALETTE

    config_path = resolve_config_path()
    port = DEFAULT_GATEWAY_PORT
    if config_path.exists():
        try:
            cfg = load_config(config_path)
            if cfg.gateway and cfg.gateway.port:
                port = cfg.gateway.port
        except Exception:
            pass

    import urllib.request

    try:
        urllib.request.urlopen(f"http://{DEFAULT_GATEWAY_BIND}:{port}/health", timeout=2)
        typer.echo(f"  {p.success}Gateway running on port {port}{p.reset}")
        typer.echo(f"  {p.muted}Use the gateway WebSocket API for detailed channel status.{p.reset}")
    except Exception:
        typer.echo(f"  {p.warn}Gateway not running. Start with 'pyclaw gateway'.{p.reset}")


def channels_add(*, channel: str, account: str = "default", name: str = "") -> None:
    """Add a channel entry to config.channels with minimal metadata."""
    p = PALETTE
    config_path = resolve_config_path()
    raw = load_config_raw(config_path) if config_path.exists() else {}
    current = dict(raw.get("channelRegistry", {}))
    key = f"{channel}:{account}"
    current[key] = {
        "channel": channel,
        "account": account,
        "name": name or key,
        "enabled": True,
    }
    raw["channelRegistry"] = current
    config = PyClawConfig.model_validate(raw)
    save_config(config, config_path)
    typer.echo(f"{p.success}Added channel config:{p.reset} {json.dumps(current[key], ensure_ascii=False)}")


def channels_remove(*, channel: str, account: str = "default") -> None:
    """Remove a channel entry from config.channels."""
    p = PALETTE
    config_path = resolve_config_path()
    if not config_path.exists():
        typer.echo(f"{p.warn}No config found.{p.reset}")
        return

    raw = load_config_raw(config_path)
    current = dict(raw.get("channelRegistry", {}))
    key = f"{channel}:{account}"
    if key not in current:
        typer.echo(f"{p.warn}Channel config not found:{p.reset} {key}")
        return
    removed = current.pop(key)
    raw["channelRegistry"] = current
    config = PyClawConfig.model_validate(raw)
    save_config(config, config_path)
    typer.echo(f"{p.success}Removed channel config:{p.reset} {json.dumps(removed, ensure_ascii=False)}")
