"""Doctor command — full health checks and diagnostics."""

from __future__ import annotations

import json
import os
import platform
import sys

import typer

from pyclaw.config.io import load_config
from pyclaw.config.paths import (
    resolve_agents_dir,
    resolve_config_path,
    resolve_credentials_dir,
    resolve_state_dir,
)
from pyclaw.constants.runtime import DEFAULT_GATEWAY_BIND, DEFAULT_GATEWAY_PORT
from pyclaw.terminal.palette import PALETTE


def doctor_command(*, non_interactive: bool = False) -> None:
    """Run full health checks and diagnostics."""
    p = PALETTE
    issues: list[str] = []
    warnings: list[str] = []
    info_items: list[str] = []

    typer.echo(f"\n{p.accent}pyclaw Doctor{p.reset}")
    typer.echo(f"{p.muted}{'─' * 50}{p.reset}\n")

    # System info
    _check_system_info(info_items)

    # Python version
    _check_python_version(issues, info_items)

    # Config
    _check_config(issues, warnings, info_items)

    # State directory
    _check_state_directory(issues, warnings, info_items)

    # Credentials
    _check_credentials(issues, warnings, info_items)

    # Auth profiles
    _check_auth_profiles(issues, warnings, info_items)

    # Sessions
    _check_sessions(issues, warnings, info_items)

    # Memory backend
    _check_memory(issues, warnings, info_items)

    # Gateway
    _check_gateway(issues, warnings, info_items)

    # Print results
    if info_items:
        typer.echo(f"{p.info}Info:{p.reset}")
        for item in info_items:
            typer.echo(f"  {p.muted}•{p.reset} {item}")
        typer.echo()

    if warnings:
        typer.echo(f"{p.warn}Warnings:{p.reset}")
        for w in warnings:
            typer.echo(f"  {p.warn}⚠{p.reset} {w}")
        typer.echo()

    if issues:
        typer.echo(f"{p.error}Issues:{p.reset}")
        for issue in issues:
            typer.echo(f"  {p.error}✗{p.reset} {issue}")
        typer.echo()
        typer.echo(f"{p.error}Found {len(issues)} issue(s) and {len(warnings)} warning(s).{p.reset}\n")
    elif warnings:
        typer.echo(f"{p.warn}Found {len(warnings)} warning(s), no critical issues.{p.reset}\n")
    else:
        typer.echo(f"{p.success}All checks passed!{p.reset}\n")


def _check_system_info(info: list[str]) -> None:
    from pyclaw import __version__

    info.append(f"pyclaw v{__version__}")
    info.append(f"Python {sys.version.split()[0]}")
    info.append(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")


def _check_python_version(issues: list[str], info: list[str]) -> None:
    v = sys.version_info
    if v < (3, 12):
        issues.append(f"Python 3.12+ required, found {v.major}.{v.minor}.{v.micro}")


def _check_config(issues: list[str], warnings: list[str], info: list[str]) -> None:
    config_path = resolve_config_path()
    info.append(f"Config: {config_path}")

    if not config_path.exists():
        issues.append("Config file not found. Run 'pyclaw setup --wizard' to create one.")
        return

    try:
        cfg = load_config(config_path)
        info.append("Config parsed successfully")
    except Exception as e:
        issues.append(f"Config parse error: {e}")
        return

    # Check providers
    if not cfg.models or not cfg.models.providers:
        warnings.append("No model providers configured")
    else:
        for name, pcfg in cfg.models.providers.items():
            if not pcfg:
                warnings.append(f"Provider '{name}' has no configuration")

    # Check for deprecated keys
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    deprecated_keys = ["apiKey", "provider", "model"]
    for key in deprecated_keys:
        if key in raw and key not in ("models",):
            warnings.append(f"Deprecated top-level config key: '{key}' (move to models.providers)")

    # Gateway config
    if cfg.gateway and cfg.gateway.port and cfg.gateway.port != DEFAULT_GATEWAY_PORT:
        info.append(f"Custom gateway port: {cfg.gateway.port}")


def _check_state_directory(issues: list[str], warnings: list[str], info: list[str]) -> None:
    state_dir = resolve_state_dir()
    info.append(f"State dir: {state_dir}")

    if not state_dir.exists():
        warnings.append(f"State directory does not exist: {state_dir}")
        return

    if not os.access(str(state_dir), os.W_OK):
        issues.append(f"State directory not writable: {state_dir}")

    # Check for stale lock files
    lock_count = len(list(state_dir.rglob("*.lock")))
    if lock_count > 0:
        warnings.append(f"Found {lock_count} lock file(s) (may be stale)")


def _check_credentials(issues: list[str], warnings: list[str], info: list[str]) -> None:
    creds_dir = resolve_credentials_dir()
    if creds_dir.is_dir():
        cred_files = list(creds_dir.iterdir())
        info.append(f"Credentials: {len(cred_files)} file(s) in {creds_dir}")
    else:
        info.append("Credentials directory: not created yet")


def _check_auth_profiles(issues: list[str], warnings: list[str], info: list[str]) -> None:
    try:
        from pyclaw.agents.auth_profiles.store import (
            load_auth_profile_store,
            resolve_auth_store_path,
        )

        path = resolve_auth_store_path()
        if path.is_file():
            store = load_auth_profile_store()
            info.append(f"Auth profiles: {len(store.profiles)} profile(s)")

            # Check for disabled profiles
            for pid, stats in store.usage_stats.items():
                if stats.disabled_until == "permanent":
                    warnings.append(f"Auth profile '{pid}' is permanently disabled: {stats.disabled_reason}")
        else:
            info.append("Auth profiles: not configured yet")
    except Exception as e:
        warnings.append(f"Auth profiles check error: {e}")


def _check_sessions(issues: list[str], warnings: list[str], info: list[str]) -> None:
    agents_dir = resolve_agents_dir()
    if not agents_dir.is_dir():
        info.append("Agents dir: not created yet")
        return

    agent_count = 0
    session_count = 0
    stale_locks = 0

    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue
        agent_count += 1
        sessions_dir = agent_dir / "sessions"
        if sessions_dir.is_dir():
            for f in sessions_dir.iterdir():
                if f.suffix == ".jsonl":
                    session_count += 1
                elif f.name.endswith(".jsonl.lock"):
                    stale_locks += 1

    info.append(f"Agents: {agent_count}, Sessions: {session_count}")
    if stale_locks > 0:
        warnings.append(
            f"Found {stale_locks} stale session lock(s). Consider running 'pyclaw setup --reset credentials'"
        )


def _check_memory(issues: list[str], warnings: list[str], info: list[str]) -> None:
    state_dir = resolve_state_dir()
    memory_db = state_dir / "memory.db"
    if memory_db.is_file():
        size_mb = memory_db.stat().st_size / (1024 * 1024)
        info.append(f"Memory DB: {size_mb:.1f} MB")
    else:
        info.append("Memory DB: not created yet")


def _check_gateway(issues: list[str], warnings: list[str], info: list[str]) -> None:
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
        resp = urllib.request.urlopen(f"http://{DEFAULT_GATEWAY_BIND}:{port}/health", timeout=2)
        if resp.status == 200:
            info.append(f"Gateway: running on port {port}")
        else:
            info.append(f"Gateway: responded with status {resp.status}")
    except Exception:
        info.append(f"Gateway: not running (port {port})")
