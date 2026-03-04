"""CLI: ``pyclaw agents bindings/bind/unbind`` — manage agent route bindings.

Ported from ``src/commands/agents.commands.bind.ts``.
"""

from __future__ import annotations

import json

import typer

from pyclaw.routing.bindings import (
    AgentBinding,
    apply_agent_bindings,
    binding_from_dict,
    binding_to_dict,
    describe_binding,
    parse_binding_spec,
    remove_agent_bindings,
)

bindings_app = typer.Typer(name="bindings", help="Manage agent route bindings.")


@bindings_app.command("list")
def list_bindings(
    agent_id: str | None = typer.Option(None, "--agent", help="Filter by agent ID."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List all agent bindings."""
    from pyclaw.config.io import load_config_raw

    raw = load_config_raw()
    raw_bindings = raw.get("bindings", [])
    bindings = [binding_from_dict(b) for b in raw_bindings if isinstance(b, dict)]

    if agent_id:
        from pyclaw.routing.session_key import normalize_agent_id

        norm = normalize_agent_id(agent_id)
        bindings = [b for b in bindings if normalize_agent_id(b.agent_id) == norm]

    if json_output:
        typer.echo(json.dumps([binding_to_dict(b) for b in bindings], indent=2))
        return

    if not bindings:
        typer.echo("No bindings configured.")
        return

    for b in bindings:
        desc = describe_binding(b)
        typer.echo(f"  {b.agent_id} -> {desc}")


@bindings_app.command()
def bind(
    spec: str = typer.Argument(..., help="Binding spec: channel[:accountId]"),
    agent_id: str = typer.Option("main", "--agent", help="Agent to bind."),
) -> None:
    """Create a new agent binding."""
    from pyclaw.config.io import load_config_raw, save_config
    from pyclaw.config.schema import PyClawConfig

    raw = load_config_raw()
    existing = [binding_from_dict(b) for b in raw.get("bindings", []) if isinstance(b, dict)]

    match = parse_binding_spec(spec)
    new_binding = AgentBinding(agent_id=agent_id, match=match)
    result = apply_agent_bindings(existing, [new_binding])

    if result.conflicts:
        for c in result.conflicts:
            typer.echo(
                f"Conflict: {describe_binding(c['binding'])} — already bound to {c['existingAgentId']}",
                err=True,
            )
        raise typer.Exit(1)

    if result.skipped and not result.added and not result.updated:
        typer.echo("Binding already exists (no changes).")
        return

    raw["bindings"] = [binding_to_dict(b) for b in result.bindings]
    config = PyClawConfig.model_validate(raw)
    save_config(config)

    for b in result.added:
        typer.echo(f"Added: {agent_id} -> {describe_binding(b)}")
    for b in result.updated:
        typer.echo(f"Updated: {agent_id} -> {describe_binding(b)}")


@bindings_app.command()
def unbind(
    spec: str | None = typer.Argument(None, help="Binding spec to remove: channel[:accountId]"),
    agent_id: str = typer.Option("main", "--agent", help="Agent to unbind."),
    all_bindings: bool = typer.Option(False, "--all", help="Remove all bindings for the agent."),
) -> None:
    """Remove an agent binding."""
    from pyclaw.config.io import load_config_raw, save_config
    from pyclaw.config.schema import PyClawConfig

    if not spec and not all_bindings:
        typer.echo("Provide a binding spec or use --all.", err=True)
        raise typer.Exit(1)

    raw = load_config_raw()
    existing = [binding_from_dict(b) for b in raw.get("bindings", []) if isinstance(b, dict)]

    specs = [parse_binding_spec(spec)] if spec else []
    remaining, removed = remove_agent_bindings(existing, specs, agent_id=agent_id, remove_all=all_bindings)

    if not removed:
        typer.echo("No matching bindings found.")
        return

    raw["bindings"] = [binding_to_dict(b) for b in remaining]
    config = PyClawConfig.model_validate(raw)
    save_config(config)

    for b in removed:
        typer.echo(f"Removed: {b.agent_id} -> {describe_binding(b)}")
