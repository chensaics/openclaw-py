"""CLI agents subcommands — list, add, remove."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer

from pyclaw.config.paths import resolve_agents_dir
from pyclaw.terminal.palette import PALETTE
from pyclaw.terminal.table import TableColumn, render_table


def agents_list() -> None:
    """List all agents."""
    p = PALETTE
    agents_dir = resolve_agents_dir()

    if not agents_dir.is_dir():
        typer.echo(f"  {p.muted}No agents directory found.{p.reset}")
        return

    rows: list[dict[str, str]] = []
    for d in sorted(agents_dir.iterdir()):
        if not d.is_dir():
            continue
        sessions_dir = d / "sessions"
        session_count = len(list(sessions_dir.glob("*.jsonl"))) if sessions_dir.is_dir() else 0
        rows.append({
            "id": d.name,
            "sessions": str(session_count),
        })

    if not rows:
        typer.echo(f"  {p.muted}No agents found.{p.reset}")
        return

    cols = [
        TableColumn(key="id", header="Agent ID", min_width=8, flex=True),
        TableColumn(key="sessions", header="Sessions", align="right", min_width=8),
    ]
    typer.echo(f"\n{p.info}Agents:{p.reset}")
    typer.echo(render_table(cols, rows))


def agents_add(agent_id: str, model: str | None = None) -> None:
    """Create a new agent."""
    p = PALETTE
    agents_dir = resolve_agents_dir()
    agent_dir = agents_dir / agent_id

    if agent_dir.exists():
        typer.echo(f"{p.error}Agent '{agent_id}' already exists.{p.reset}")
        raise typer.Exit(1)

    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "sessions").mkdir(exist_ok=True)

    if model:
        config = {"model": model}
        (agent_dir / "config.json").write_text(
            json.dumps(config, indent=2) + "\n", encoding="utf-8"
        )

    typer.echo(f"{p.success}Created agent '{agent_id}'.{p.reset}")


def agents_remove(agent_id: str, force: bool = False) -> None:
    """Remove an agent and all its data."""
    p = PALETTE
    agents_dir = resolve_agents_dir()
    agent_dir = agents_dir / agent_id

    if not agent_dir.is_dir():
        typer.echo(f"{p.error}Agent '{agent_id}' not found.{p.reset}")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Remove agent '{agent_id}' and all its sessions?")
        if not confirm:
            typer.echo("Cancelled.")
            return

    shutil.rmtree(agent_dir)
    typer.echo(f"{p.success}Removed agent '{agent_id}'.{p.reset}")
