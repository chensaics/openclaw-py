"""CLI config subcommands — get, set, list."""

from __future__ import annotations

import json
from typing import Any

import typer

from pyclaw.terminal.palette import PALETTE


def config_get(key: str) -> None:
    """Get a configuration value by dotted key path."""
    from pyclaw.config.io import load_config
    from pyclaw.config.paths import resolve_config_path

    p = PALETTE
    config_path = resolve_config_path()
    if not config_path.exists():
        typer.echo(f"{p.error}Config not found. Run 'pyclaw setup --wizard'.{p.reset}")
        raise typer.Exit(1)

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    value = _get_nested(raw, key)
    if value is None:
        typer.echo(f"{p.warn}Key '{key}' not found.{p.reset}")
        raise typer.Exit(1)

    if isinstance(value, (dict, list)):
        typer.echo(json.dumps(value, indent=2))
    else:
        typer.echo(str(value))


def config_set(key: str, value: str) -> None:
    """Set a configuration value by dotted key path."""
    from pyclaw.config.io import load_config, save_config
    from pyclaw.config.paths import resolve_config_path

    p = PALETTE
    config_path = resolve_config_path()
    if not config_path.exists():
        typer.echo(f"{p.error}Config not found. Run 'pyclaw setup --wizard'.{p.reset}")
        raise typer.Exit(1)

    raw = json.loads(config_path.read_text(encoding="utf-8"))

    # Parse value: try JSON first, then string
    parsed: Any
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = value

    _set_nested(raw, key, parsed)
    config_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    typer.echo(f"{p.success}Set {key} = {value}{p.reset}")


def config_list() -> None:
    """List all configuration values."""
    from pyclaw.config.paths import resolve_config_path

    p = PALETTE
    config_path = resolve_config_path()
    if not config_path.exists():
        typer.echo(f"{p.warn}Config not found.{p.reset}")
        return

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    _print_flat(raw, "")


def _get_nested(data: dict[str, Any], key: str) -> Any:
    parts = key.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _set_nested(data: dict[str, Any], key: str, value: Any) -> None:
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _print_flat(data: dict[str, Any], prefix: str) -> None:
    p = PALETTE
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            _print_flat(value, full_key)
        else:
            display = json.dumps(value) if isinstance(value, (list, bool)) else str(value)
            typer.echo(f"  {p.muted}{full_key}{p.reset} = {display}")
