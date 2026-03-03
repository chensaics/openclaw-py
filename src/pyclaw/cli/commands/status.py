"""Full status command — channels, sessions, gateway health, table output."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

import typer

from pyclaw.config.io import load_config
from pyclaw.config.paths import resolve_agents_dir, resolve_config_path, resolve_state_dir
from pyclaw.terminal.palette import PALETTE
from pyclaw.terminal.table import TableColumn, render_table


@dataclass
class SessionStatus:
    agent_id: str = ""
    key: str = ""
    session_id: str = ""
    updated_at: str = ""
    age: str = ""
    model: str = ""
    context_tokens: int = 0
    total_tokens: int = 0
    remaining_tokens: int = 0
    percent_used: float = 0.0


@dataclass
class StatusSummary:
    version: str = ""
    config_path: str = ""
    state_dir: str = ""
    config_valid: bool = False
    providers: list[str] = field(default_factory=list)
    default_model: str = ""
    gateway_port: int = 18789
    gateway_running: bool = False
    channels: list[dict[str, str]] = field(default_factory=list)
    sessions: list[SessionStatus] = field(default_factory=list)
    agent_count: int = 0


def scan_status(*, output_json: bool = False, deep: bool = False) -> StatusSummary:
    """Gather system status from config, sessions, and gateway."""
    from pyclaw import __version__

    summary = StatusSummary(version=__version__)
    config_path = resolve_config_path()
    state_dir = resolve_state_dir()
    summary.config_path = str(config_path)
    summary.state_dir = str(state_dir)

    # Config
    if config_path.exists():
        try:
            cfg = load_config(config_path)
            summary.config_valid = True
            if cfg.models:
                if cfg.models.providers:
                    summary.providers = list(cfg.models.providers.keys())
                if cfg.models.default:
                    summary.default_model = cfg.models.default
            if cfg.gateway and cfg.gateway.port:
                summary.gateway_port = cfg.gateway.port
        except Exception:
            summary.config_valid = False

    # Agents and sessions
    agents_dir = resolve_agents_dir()
    if agents_dir.is_dir():
        agent_dirs = [d for d in agents_dir.iterdir() if d.is_dir()]
        summary.agent_count = len(agent_dirs)

        for agent_dir in agent_dirs:
            sessions_dir = agent_dir / "sessions"
            if not sessions_dir.is_dir():
                continue
            for session_file in sorted(sessions_dir.glob("*.jsonl"))[:10]:
                try:
                    stat = session_file.stat()
                    age = _format_age(stat.st_mtime)
                    summary.sessions.append(
                        SessionStatus(
                            agent_id=agent_dir.name,
                            key=session_file.stem,
                            updated_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                            age=age,
                        )
                    )
                except OSError:
                    continue

    # Gateway probe
    if deep:
        summary.gateway_running = _probe_gateway(summary.gateway_port)

    return summary


def _probe_gateway(port: int) -> bool:
    """Quick HTTP probe to check if gateway is running."""
    import urllib.request

    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
        return cast(bool, resp.status == 200)
    except Exception:
        return False


def _format_age(mtime: float) -> str:
    delta = datetime.now(UTC).timestamp() - mtime
    if delta < 60:
        return f"{int(delta)}s"
    if delta < 3600:
        return f"{int(delta / 60)}m"
    if delta < 86400:
        return f"{int(delta / 3600)}h"
    return f"{int(delta / 86400)}d"


def status_command(
    *,
    output_json: bool = False,
    deep: bool = False,
    all_info: bool = False,
    usage: bool = False,
) -> None:
    """Execute the status command."""
    p = PALETTE
    summary = scan_status(output_json=output_json, deep=deep or all_info)

    usage_snapshot: dict[str, Any] | None = None
    if usage:
        try:
            from pyclaw.infra.session_cost import aggregate_usage

            usage_snapshot = aggregate_usage(days=7)
        except Exception:
            usage_snapshot = None

    if output_json:
        import dataclasses

        def _ser(obj: Any) -> Any:
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                return dataclasses.asdict(obj)
            return str(obj)

        payload = dataclasses.asdict(summary)
        if usage_snapshot is not None:
            payload["usage"] = usage_snapshot
        typer.echo(json.dumps(payload, indent=2, default=_ser))
        return

    # Header
    typer.echo(f"\n{p.accent}pyclaw{p.reset} v{summary.version}")
    typer.echo(f"{p.muted}{'─' * 50}{p.reset}")

    # Config
    config_status = (
        f"{p.success}valid{p.reset}" if summary.config_valid else f"{p.error}invalid{p.reset}"
    )
    typer.echo(f"  Config:    {config_status} ({summary.config_path})")
    typer.echo(f"  State dir: {summary.state_dir}")

    # Providers
    if summary.providers:
        typer.echo(f"  Providers: {', '.join(summary.providers)}")
    else:
        typer.echo(f"  Providers: {p.warn}(none configured){p.reset}")

    if summary.default_model:
        typer.echo(f"  Model:     {summary.default_model}")

    # Gateway
    if deep or all_info:
        gw_status = (
            f"{p.success}running{p.reset}"
            if summary.gateway_running
            else f"{p.error}not running{p.reset}"
        )
        typer.echo(f"  Gateway:   {gw_status} (port {summary.gateway_port})")

    # Agents
    typer.echo(f"  Agents:    {summary.agent_count}")

    # Sessions table
    if summary.sessions:
        typer.echo(f"\n{p.info}Sessions:{p.reset}")
        cols = [
            TableColumn(key="agent", header="Agent", min_width=6),
            TableColumn(key="session", header="Session", min_width=10, max_width=30, flex=True),
            TableColumn(key="age", header="Age", align="right", min_width=4),
        ]
        rows = [
            {
                "agent": s.agent_id,
                "session": s.key,
                "age": s.age,
            }
            for s in summary.sessions
        ]
        typer.echo(render_table(cols, rows))
    else:
        typer.echo(f"\n  {p.muted}No sessions found.{p.reset}")

    if usage:
        typer.echo(f"\n{p.info}Usage (7d):{p.reset}")
        if usage_snapshot:
            typer.echo(
                f"  Sessions: {usage_snapshot.get('sessions', 0)} | "
                f"Calls: {usage_snapshot.get('calls', 0)}"
            )
            typer.echo(
                f"  Tokens: {usage_snapshot.get('total_input_tokens', 0)} in / "
                f"{usage_snapshot.get('total_output_tokens', 0)} out"
            )
            typer.echo(f"  Estimated cost: {usage_snapshot.get('estimated_cost', '$0.0000')}")
            providers = usage_snapshot.get("by_provider", {})
            if isinstance(providers, dict) and providers:
                typer.echo("  Providers:")
                for provider in sorted(providers):
                    row = providers[provider]
                    typer.echo(
                        f"    - {provider}: {row.get('total_tokens', 0)} tokens, "
                        f"{row.get('estimated_cost', '$0.0000')}"
                    )
        else:
            typer.echo(f"  {p.muted}No usage data available.{p.reset}")

    typer.echo()
