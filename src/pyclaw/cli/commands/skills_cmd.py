"""CLI skills subcommands — list, search, install, remove."""

from __future__ import annotations

import asyncio

import typer

from pyclaw.terminal.palette import PALETTE


def skills_list_command() -> None:
    """List installed skills."""
    from pyclaw.agents.skills.marketplace import list_installed_skills

    p = PALETTE
    skills = list_installed_skills()

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
        fetch_skill_content,
        fetch_skill_from_url,
        install_skill,
    )

    p = PALETTE
    is_url = name.startswith("http://") or name.startswith("https://")

    typer.echo(f"{p.info}Fetching skill '{name}'...{p.reset}")

    if is_url:
        content = asyncio.run(fetch_skill_from_url(name))
        skill_name = name.rstrip("/").rsplit("/", 1)[-1]
        if skill_name == "SKILL.md":
            skill_name = name.rstrip("/").rsplit("/", 2)[-2]
    else:
        content = asyncio.run(fetch_skill_content(name))
        skill_name = name

    if content is None:
        typer.echo(f"{p.error}Skill '{name}' not found.{p.reset}")
        raise typer.Exit(1)

    try:
        path = install_skill(skill_name, content, force=force)
        typer.echo(f"{p.success}Installed skill '{skill_name}' → {path}{p.reset}")
    except FileExistsError as exc:
        typer.echo(f"{p.warn}{exc}{p.reset}")
        raise typer.Exit(1)


def skills_remove_command(name: str) -> None:
    """Remove an installed skill."""
    from pyclaw.agents.skills.marketplace import remove_skill

    p = PALETTE

    if remove_skill(name):
        typer.echo(f"{p.success}Removed skill '{name}'.{p.reset}")
    else:
        typer.echo(f"{p.warn}Skill '{name}' not found.{p.reset}")
