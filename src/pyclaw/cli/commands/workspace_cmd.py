"""CLI workspace subcommands — sync and diff templates."""

from __future__ import annotations

import typer

from pyclaw.terminal.palette import PALETTE


def workspace_sync_command(*, force: bool = False) -> None:
    """Sync workspace templates — create missing files, optionally overwrite."""
    from pyclaw.agents.workspace_sync import sync_templates

    p = PALETTE
    results = sync_templates(force=force)

    if not results["created"] and not results["updated"] and not results["skipped"]:
        typer.echo(f"{p.success}Workspace is up to date.{p.reset}")
        return

    if results["created"]:
        typer.echo(f"\n{p.success}Created:{p.reset}")
        for f in results["created"]:
            typer.echo(f"  + {f}")

    if results["updated"]:
        typer.echo(f"\n{p.info}Updated:{p.reset}")
        for f in results["updated"]:
            typer.echo(f"  ~ {f}")

    if results["skipped"]:
        typer.echo(f"\n{p.muted}Skipped (already modified, use --force to overwrite):{p.reset}")
        for f in results["skipped"]:
            typer.echo(f"  - {f}")

    typer.echo()


def workspace_diff_command() -> None:
    """Show differences between workspace files and templates."""
    from pyclaw.agents.workspace_sync import diff_templates

    p = PALETTE
    diffs = diff_templates()

    if not diffs:
        typer.echo(f"{p.success}Workspace matches templates — no differences.{p.reset}")
        return

    for d in diffs:
        status = d["status"]
        icon = "?" if status == "missing" else "~"
        label = "missing" if status == "missing" else "modified"
        typer.echo(f"  {icon} {d['name']}  {p.muted}({label}){p.reset}")
