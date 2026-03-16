"""Setup / onboarding command — interactive wizard and non-interactive modes.

Ported from ``src/commands/onboard-interactive.ts``.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import typer

from pyclaw.cli.commands.auth_providers import PROVIDER_SPECS, AuthMethod
from pyclaw.config.defaults import get_provider_defaults
from pyclaw.config.paths import resolve_config_path, resolve_credentials_dir, resolve_state_dir
from pyclaw.constants.runtime import DEFAULT_GATEWAY_PORT

_SELF_HOSTED_PROVIDERS = {"ollama", "vllm", "litellm"}

_PROVIDER_GROUPS: list[tuple[str, list[str]]] = [
    (
        "Global",
        [
            "anthropic",
            "openai",
            "google",
            "xai",
            "openrouter",
            "together",
            "groq",
            "perplexity",
            "fireworks",
            "huggingface",
            "bedrock",
            "nvidia",
            "copilot",
        ],
    ),
    (
        "China",
        [
            "deepseek",
            "qwen",
            "moonshot",
            "volcengine",
            "zhipu",
            "minimax",
            "qianfan",
            "byteplus",
            "xiaomi",
        ],
    ),
    (
        "Self-hosted / Proxy",
        [
            "ollama",
            "vllm",
            "litellm",
        ],
    ),
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


def _build_provider_list() -> list[tuple[str, str, str]]:
    """Build a flat (provider_id, display_name, env_var) list from groups."""
    items: list[tuple[str, str, str]] = []
    for _group, ids in _PROVIDER_GROUPS:
        for pid in ids:
            spec = PROVIDER_SPECS.get(pid)
            if spec:
                items.append((pid, spec.display_name, spec.env_var))
    return items


def _run_wizard(config_path: Path) -> None:
    """Interactive setup wizard."""
    import json

    providers = _build_provider_list()

    typer.echo("\n  pyclaw Setup Wizard\n")
    typer.echo("  Select your AI provider:\n")

    seq = 0
    for group_name, ids in _PROVIDER_GROUPS:
        typer.echo(f"    [{group_name}]")
        for pid in ids:
            spec = PROVIDER_SPECS.get(pid)
            if not spec:
                continue
            seq += 1
            typer.echo(f"      {seq:>2}. {spec.display_name}")
        typer.echo("")

    choice = typer.prompt("  Provider number", default="1")
    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(providers)):
            idx = 0
    except ValueError:
        idx = 0

    provider_id, provider_label, env_var = providers[idx]
    spec = PROVIDER_SPECS[provider_id]

    config: dict[str, Any] = {}

    provider_cfg: dict[str, Any] = {}

    if spec.auth_method == AuthMethod.NONE:
        typer.echo(f"\n  {provider_label} selected (no API key required).")
    elif env_var:
        env_val = os.environ.get(env_var, "").strip()
        if env_val:
            typer.echo(f"\n  Found {env_var} in environment.")
            use_env = typer.confirm("  Use this key?", default=True)
            if use_env:
                provider_cfg["apiKey"] = f"${{{env_var}}}"
            else:
                api_key = typer.prompt(f"  Enter {provider_label} API key", hide_input=True)
                provider_cfg["apiKey"] = api_key
        else:
            api_key = typer.prompt(f"\n  Enter {provider_label} API key", hide_input=True)
            provider_cfg["apiKey"] = api_key
    else:
        api_key = typer.prompt(f"\n  Enter {provider_label} API key", hide_input=True)
        provider_cfg["apiKey"] = api_key

    if spec.api_key_url:
        typer.echo(f"  Get your key at: {spec.api_key_url}")

    default_base, default_model = get_provider_defaults(provider_id)
    if provider_id in _SELF_HOSTED_PROVIDERS and default_base:
        base_url = typer.prompt(
            f"\n  Base URL for {provider_label}",
            default=default_base,
        )
        provider_cfg["baseUrl"] = base_url

    if provider_id in _SELF_HOSTED_PROVIDERS:
        hint = default_model or "your-model-name"
        model_name = typer.prompt(
            f"\n  Model name (e.g. the model served by {provider_label})",
            default=hint,
        )
        if model_name and model_name != hint or model_name:
            provider_cfg["models"] = [{"id": model_name, "name": model_name}]

    config["models"] = {"providers": {provider_id: provider_cfg}}

    config["gateway"] = {"port": DEFAULT_GATEWAY_PORT}

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

    config: dict[str, Any] = {"gateway": {"port": DEFAULT_GATEWAY_PORT}}

    for spec in PROVIDER_SPECS.values():
        if spec.env_var and os.environ.get(spec.env_var, "").strip():
            config["models"] = {"providers": {spec.provider_id: {"apiKey": f"${{{spec.env_var}}}"}}}
            typer.echo(f"Detected {spec.display_name} via {spec.env_var}")
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
