"""Setup / onboarding command — interactive wizard and non-interactive modes.

Ported from ``src/commands/onboard-interactive.ts``.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import typer

from pyclaw.config.paths import resolve_config_path, resolve_credentials_dir, resolve_state_dir


_PROVIDERS = [
    ("anthropic", "Anthropic (Claude)", "ANTHROPIC_API_KEY"),
    ("openai", "OpenAI (GPT)", "OPENAI_API_KEY"),
    ("google", "Google (Gemini)", "GOOGLE_API_KEY"),
    ("openrouter", "OpenRouter", "OPENROUTER_API_KEY"),
    ("ollama", "Ollama (local)", None),
]


def setup_command(
    *,
    wizard: bool = False,
    non_interactive: bool = False,
    accept_risk: bool = False,
    reset: str | None = None,
) -> None:
    """Run the setup/onboarding flow."""

    if reset:
        _handle_reset(reset)
        return

    state_dir = resolve_state_dir()
    config_path = resolve_config_path()
    state_dir.mkdir(parents=True, exist_ok=True)

    if non_interactive:
        _run_non_interactive(config_path, accept_risk=accept_risk)
        return

    if wizard or not config_path.exists():
        _run_wizard(config_path)
        return

    # Default: just ensure dirs exist
    if not config_path.exists():
        config_path.write_text("{}\n")
        typer.echo(f"Created config at {config_path}")
    else:
        typer.echo(f"Config already exists at {config_path}")

    typer.echo(f"State directory: {state_dir}")


def _run_wizard(config_path: Path) -> None:
    """Interactive setup wizard."""
    import json

    typer.echo("\n  pyclaw Setup Wizard\n")
    typer.echo("  Select your AI provider:\n")

    for i, (pid, label, _) in enumerate(_PROVIDERS, 1):
        typer.echo(f"    {i}. {label}")

    choice = typer.prompt("\n  Provider number", default="1")
    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(_PROVIDERS)):
            idx = 0
    except ValueError:
        idx = 0

    provider_id, provider_label, env_var = _PROVIDERS[idx]

    config: dict = {}

    if env_var:
        # Check env first
        env_val = os.environ.get(env_var, "").strip()
        if env_val:
            typer.echo(f"\n  Found {env_var} in environment.")
            use_env = typer.confirm("  Use this key?", default=True)
            if use_env:
                config["models"] = {"providers": {provider_id: {"apiKey": f"${{{env_var}}}"}}}
            else:
                api_key = typer.prompt(f"  Enter {provider_label} API key", hide_input=True)
                config["models"] = {"providers": {provider_id: {"apiKey": api_key}}}
        else:
            if provider_id != "ollama":
                api_key = typer.prompt(f"\n  Enter {provider_label} API key", hide_input=True)
                config["models"] = {"providers": {provider_id: {"apiKey": api_key}}}
    else:
        # Ollama — no key needed
        typer.echo(f"\n  {provider_label} selected (no API key required).")
        config["models"] = {"providers": {provider_id: {}}}

    # Gateway port
    typer.echo("")
    config["gateway"] = {"port": 18789}

    # Write config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    typer.echo(f"\n  Config written to {config_path}")
    typer.echo("  Run 'pyclaw gateway' to start.\n")


def _run_non_interactive(config_path: Path, *, accept_risk: bool = False) -> None:
    """Non-interactive setup using environment variables."""
    import json

    if not accept_risk:
        typer.echo("Error: --non-interactive requires --accept-risk flag.")
        raise typer.Exit(1)

    config: dict = {"gateway": {"port": 18789}}

    # Auto-detect provider from env
    for provider_id, label, env_var in _PROVIDERS:
        if env_var and os.environ.get(env_var, "").strip():
            config["models"] = {"providers": {provider_id: {"apiKey": f"${{{env_var}}}"}}}
            typer.echo(f"Detected {label} via {env_var}")
            break
    else:
        typer.echo("Warning: no provider API key found in environment.")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    typer.echo(f"Config written to {config_path}")


def _handle_reset(scope: str) -> None:
    """Handle --reset with scope: config, credentials, or full."""
    config_path = resolve_config_path()
    creds_dir = resolve_credentials_dir()
    state_dir = resolve_state_dir()

    if scope == "config":
        if config_path.exists():
            config_path.unlink()
            typer.echo(f"Removed config: {config_path}")
        else:
            typer.echo("No config to remove.")

    elif scope == "credentials":
        if creds_dir.exists():
            shutil.rmtree(creds_dir)
            typer.echo(f"Removed credentials: {creds_dir}")
        else:
            typer.echo("No credentials to remove.")

    elif scope == "full":
        confirm = typer.confirm(
            f"This will delete all pyclaw data at {state_dir}. Continue?",
            default=False,
        )
        if confirm:
            if state_dir.exists():
                shutil.rmtree(state_dir)
                typer.echo(f"Removed all data: {state_dir}")
        else:
            typer.echo("Cancelled.")

    else:
        typer.echo(f"Unknown reset scope: {scope}. Use 'config', 'credentials', or 'full'.")
        raise typer.Exit(1)
