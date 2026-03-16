"""CLI skills subcommands — list, search, install, remove."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from pyclaw.terminal.palette import PALETTE


def skills_list_command() -> None:
    """List installed skills."""
    from pyclaw.agents.skills.marketplace import list_installed_skills

    p = PALETTE
    skills = list_installed_skills(workspace_dir=Path.cwd())

    if not skills:
        typer.echo(f"{p.muted}No skills installed.{p.reset}")
        typer.echo("Use 'pyclaw skills search <query>' to find skills.")
        return

    typer.echo(f"\n{p.info}Installed Skills:{p.reset}\n")
    for s in skills:
        typer.echo(f"  • {s['name']}  {p.muted}({s['source']}){p.reset}")
        typer.echo(f"    {p.muted}{s['path']}{p.reset}")
    typer.echo()


def skills_search_command(query: str) -> None:
    """Search for skills in the ClawHub marketplace."""
    from pyclaw.agents.skills.marketplace import search_skills

    p = PALETTE
    typer.echo(f"{p.info}Searching ClawHub for '{query}'...{p.reset}")

    results = asyncio.run(search_skills(query))

    if not results:
        typer.echo(f"{p.muted}No skills found matching '{query}'.{p.reset}")
        return

    typer.echo(f"\n{p.info}Found {len(results)} skill(s):{p.reset}\n")
    for skill in results:
        typer.echo(f"  • {skill.name}")
        if skill.description:
            typer.echo(f"    {p.muted}{skill.description}{p.reset}")
        if skill.url:
            typer.echo(f"    {p.muted}{skill.url}{p.reset}")
    typer.echo("\n  Install with: pyclaw skills install <name>")


def skills_install_command(name: str, *, force: bool = False) -> None:
    """Install a skill from ClawHub or a URL."""
    from pyclaw.agents.skills.marketplace import (
        fetch_skill_bundle_from_url,
        fetch_skill_content,
        guess_skill_name_from_url,
        install_skill,
        install_skill_bundle,
        install_skill_via_clawhub,
    )

    p = PALETTE
    is_url = name.startswith("http://") or name.startswith("https://")

    typer.echo(f"{p.info}Fetching skill '{name}'...{p.reset}")

    if is_url:
        bundle_result = asyncio.run(fetch_skill_bundle_from_url(name))
        if bundle_result is None:
            typer.echo(f"{p.error}Skill URL '{name}' not found or invalid.{p.reset}")
            raise typer.Exit(1)
        skill_name, files = bundle_result
        if not skill_name:
            skill_name = guess_skill_name_from_url(name)
        try:
            path = install_skill_bundle(skill_name, files, workspace_dir=Path.cwd(), force=force)
            typer.echo(f"{p.success}Installed skill '{skill_name}' → {path}{p.reset}")
            return
        except (FileExistsError, ValueError) as exc:
            typer.echo(f"{p.warn}{exc}{p.reset}")
            raise typer.Exit(1) from exc
    else:
        content = asyncio.run(fetch_skill_content(name))
        if content is not None:
            try:
                path = install_skill(name, content, workspace_dir=Path.cwd(), force=force)
                typer.echo(f"{p.success}Installed skill '{name}' → {path}{p.reset}")
                return
            except FileExistsError as exc:
                typer.echo(f"{p.warn}{exc}{p.reset}")
                raise typer.Exit(1) from exc
        ok, msg = install_skill_via_clawhub(name)
        if ok:
            typer.echo(f"{p.success}Installed skill '{name}' via clawhub.{p.reset}")
            if msg:
                typer.echo(f"{p.muted}{msg}{p.reset}")
            return
        typer.echo(f"{p.error}Skill '{name}' not found.{p.reset}")
        if msg:
            typer.echo(f"{p.muted}{msg}{p.reset}")
        raise typer.Exit(1)

    # unreachable; retained for defensive compatibility
    typer.echo(f"{p.error}Skill '{name}' installation flow failed unexpectedly.{p.reset}")
    raise typer.Exit(1)


def skills_remove_command(name: str) -> None:
    """Remove an installed skill."""
    from pyclaw.agents.skills.marketplace import remove_skill

    p = PALETTE

    if remove_skill(name, workspace_dir=Path.cwd()):
        typer.echo(f"{p.success}Removed skill '{name}'.{p.reset}")
    else:
        typer.echo(f"{p.warn}Skill '{name}' not found.{p.reset}")


def skills_sync_command() -> None:
    """Sync installed skills via clawhub when available."""
    from pyclaw.agents.skills.marketplace import clawhub_sync

    p = PALETTE
    ok, out = clawhub_sync()
    if ok:
        typer.echo(f"{p.success}clawhub sync complete.{p.reset}")
        if out:
            typer.echo(out)
        return
    typer.echo(f"{p.warn}clawhub sync unavailable or failed.{p.reset}")
    if out:
        typer.echo(f"{p.muted}{out}{p.reset}")


def skills_update_command() -> None:
    """Update all clawhub-managed skills when available."""
    from pyclaw.agents.skills.marketplace import clawhub_update_all

    p = PALETTE
    ok, out = clawhub_update_all()
    if ok:
        typer.echo(f"{p.success}clawhub update --all complete.{p.reset}")
        if out:
            typer.echo(out)
        return
    typer.echo(f"{p.warn}clawhub update unavailable or failed.{p.reset}")
    if out:
        typer.echo(f"{p.muted}{out}{p.reset}")


def skills_inspect_command(name: str) -> None:
    """Inspect a skill via clawhub when available."""
    from pyclaw.agents.skills.marketplace import clawhub_inspect

    p = PALETTE
    ok, out = clawhub_inspect(name)
    if ok:
        typer.echo(out or f"Skill '{name}' inspected.")
        return
    typer.echo(f"{p.warn}clawhub inspect unavailable or failed for '{name}'.{p.reset}")
    if out:
        typer.echo(f"{p.muted}{out}{p.reset}")


def skills_run_command(
    name: str,
    *,
    payload_json: str = "{}",
    output_json: bool = True,
) -> None:
    """Run a bundled skill and print structured output."""
    from pyclaw.agents.skills.runner import parse_payload, run_skill

    p = PALETTE
    try:
        payload = parse_payload(payload_json)
    except ValueError as exc:
        typer.echo(f"{p.error}{exc}{p.reset}")
        raise typer.Exit(1) from exc

    try:
        result = run_skill(name, workspace_dir=Path.cwd(), payload=payload)
    except KeyError as exc:
        typer.echo(f"{p.error}{exc}{p.reset}")
        raise typer.Exit(1) from exc

    if output_json:
        import json

        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return

    typer.echo(f"{p.info}Skill: {result.get('skill', name)}{p.reset}")
    typer.echo(f"Status: {result.get('status', 'ok')}")
    summary = result.get("summary")
    if isinstance(summary, str) and summary:
        typer.echo(summary)
