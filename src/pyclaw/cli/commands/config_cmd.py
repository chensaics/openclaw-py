"""CLI config subcommands — get, set, list."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from pyclaw.terminal.palette import PALETTE


def config_get(key: str) -> None:
    """Get a configuration value by dotted key path."""
    from pyclaw.config.io import load_config_raw
    from pyclaw.config.paths import resolve_config_path

    p = PALETTE
    config_path = resolve_config_path()
    if not config_path.exists():
        typer.echo(f"{p.error}Config not found. Run 'pyclaw setup --wizard'.{p.reset}")
        raise typer.Exit(1)

    raw = load_config_raw(config_path)
    value = _get_nested(raw, key)
    if value is None:
        typer.echo(f"{p.warn}Key '{key}' not found.{p.reset}")
        raise typer.Exit(1)

    if isinstance(value, dict | list):
        typer.echo(json.dumps(value, indent=2))
    else:
        typer.echo(str(value))


def config_set(key: str, value: str) -> None:
    """Set a configuration value by dotted key path."""
    from pyclaw.config.io import load_config_raw
    from pyclaw.config.paths import resolve_config_path

    p = PALETTE
    config_path = resolve_config_path()
    if not config_path.exists():
        typer.echo(f"{p.error}Config not found. Run 'pyclaw setup --wizard'.{p.reset}")
        raise typer.Exit(1)

    raw = load_config_raw(config_path)

    # Parse value: try JSON first, then string
    parsed: Any
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = value

    _set_nested(raw, key, parsed)
    _write_raw_config(config_path, raw)
    typer.echo(f"{p.success}Set {key} = {value}{p.reset}")


def config_validate() -> None:
    """Validate the pyclaw configuration file."""
    from pyclaw.config.io import load_config
    from pyclaw.config.paths import resolve_config_path

    config_path = resolve_config_path()
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        raise SystemExit(1)

    try:
        cfg = load_config(config_path)
        print(f"Config valid: {config_path}")
        # Show summary
        if cfg.models and cfg.models.providers:
            print(f"  Providers: {', '.join(cfg.models.providers.keys())}")
        if cfg.channels:
            print("  Channels: configured")
    except Exception as e:
        print(f"Config invalid: {e}")
        raise SystemExit(1)


def config_list() -> None:
    """List all configuration values."""
    from pyclaw.config.io import load_config_raw
    from pyclaw.config.paths import resolve_config_path

    p = PALETTE
    config_path = resolve_config_path()
    if not config_path.exists():
        typer.echo(f"{p.warn}Config not found.{p.reset}")
        return

    raw = load_config_raw(config_path)
    _print_flat(raw, "")


def _write_raw_config(config_path: Path, raw: dict[str, Any]) -> None:
    """Persist a raw config dict as normalized JSON text."""
    config_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
            display = json.dumps(value) if isinstance(value, list | bool) else str(value)
            typer.echo(f"  {p.muted}{full_key}{p.reset} = {display}")
