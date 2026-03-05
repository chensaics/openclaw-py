"""pyclaw CLI application."""

import typer

from pyclaw import __version__

app = typer.Typer(
    name="pyclaw",
    help="Multi-channel AI gateway with extensible messaging integrations.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pyclaw {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    pass


@app.command()
def setup(
    wizard: bool = typer.Option(False, "--wizard", help="Interactive setup wizard."),
    non_interactive: bool = typer.Option(
        False, "--non-interactive", help="Non-interactive setup (use defaults/env vars)."
    ),
    accept_risk: bool = typer.Option(False, "--accept-risk", help="Accept risk for non-interactive setup."),
    reset: str | None = typer.Option(None, "--reset", help="Reset scope: 'config', 'credentials', or 'full'."),
) -> None:
    """Initialize configuration and workspace."""
    from pyclaw.cli.commands.setup import setup_command

    setup_command(wizard=wizard, non_interactive=non_interactive, accept_risk=accept_risk, reset=reset)


@app.command()
def doctor(
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Skip interactive prompts."),
) -> None:
    """Run health checks and diagnostics."""
    from pyclaw.cli.commands.doctor import doctor_command

    doctor_command(non_interactive=non_interactive)


@app.command()
def agent(
    message: str = typer.Argument(..., help="Message to send to the agent."),
    to: str = typer.Option("", "--to", help="Delivery target/session destination."),
    session_id: str = typer.Option("", "--session-id", help="Explicit session ID."),
    thinking: str = typer.Option("", "--thinking", help="Thinking level (off|minimal|low|medium|high|xhigh)."),
    verbose: str = typer.Option("off", "--verbose", help="Verbosity mode (on|full|off)."),
    channel: str = typer.Option("", "--channel", help="Reply channel for delivery."),
    local: bool = typer.Option(False, "--local", help="Run in local/embedded mode."),
    deliver: bool = typer.Option(False, "--deliver", help="Deliver response to channel target."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
    timeout: int = typer.Option(120, "--timeout", help="Timeout in seconds."),
    provider: str = typer.Option("anthropic", help="LLM provider."),
    model: str = typer.Option("claude-sonnet-4-6", help="Model ID."),
    api_key: str | None = typer.Option(None, envvar="OPENAI_API_KEY", help="API key."),
    base_url: str | None = typer.Option(None, help="Custom API base URL."),
    agent_id: str = typer.Option("main", "--agent", help="Agent ID."),
) -> None:
    """Run a single agent turn with the given message."""
    from pyclaw.cli.commands.agent import agent_command

    agent_command(
        message=message,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        agent_id=agent_id,
        session_id=session_id,
        to=to,
        thinking=thinking,
        verbose=verbose,
        channel=channel,
        local=local,
        deliver=deliver,
        output_json=output_json,
        timeout=timeout,
    )


gateway_app = typer.Typer(name="gateway", help="Gateway management commands.")
app.add_typer(gateway_app)


@gateway_app.callback(invoke_without_command=True)
def gateway_root(
    ctx: typer.Context,
    port: int = typer.Option(18789, help="Port to listen on."),
    bind: str = typer.Option("127.0.0.1", help="Address to bind to."),
    auth_token: str | None = typer.Option(None, envvar="PYCLAW_AUTH_TOKEN", help="Auth token."),
) -> None:
    """Start the gateway server (default) or manage it with subcommands."""
    if ctx.invoked_subcommand:
        return
    from pyclaw.cli.commands.gateway_cmd import gateway_run_command

    gateway_run_command(port=port, bind=bind, auth_token=auth_token)


@gateway_app.command("run")
def gateway_run_cmd(
    port: int = typer.Option(18789, help="Port to listen on."),
    bind: str = typer.Option("127.0.0.1", help="Address to bind to."),
    auth_token: str | None = typer.Option(None, envvar="PYCLAW_AUTH_TOKEN", help="Auth token."),
) -> None:
    """Start the pyclaw gateway server."""
    from pyclaw.cli.commands.gateway_cmd import gateway_run_command

    gateway_run_command(port=port, bind=bind, auth_token=auth_token)


@gateway_app.command("status")
def gateway_status_cmd(
    url: str = typer.Option("", "--url", help="Gateway WebSocket URL."),
    token: str | None = typer.Option(None, "--token", help="Auth token."),
    password: str | None = typer.Option(None, "--password", help="Auth password."),
    timeout: int = typer.Option(10000, "--timeout", help="Timeout in ms."),
    no_probe: bool = typer.Option(False, "--no-probe", help="Skip RPC probe."),
    deep: bool = typer.Option(False, "--deep", help="Include extended info."),
    output_json: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    """Show gateway service + probe status."""
    from pyclaw.cli.commands.gateway_cmd import gateway_status_command

    gateway_status_command(
        url=url,
        token=token,
        password=password,
        timeout_ms=timeout,
        no_probe=no_probe,
        deep=deep,
        output_json=output_json,
    )


@gateway_app.command("probe")
def gateway_probe_cmd(
    url: str = typer.Option("", "--url", help="Gateway WebSocket URL."),
    token: str | None = typer.Option(None, "--token", help="Auth token."),
    password: str | None = typer.Option(None, "--password", help="Auth password."),
    timeout: int = typer.Option(10000, "--timeout", help="Timeout in ms."),
    output_json: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    """Probe gateway connectivity."""
    from pyclaw.cli.commands.gateway_cmd import gateway_probe_command

    gateway_probe_command(url=url, token=token, password=password, timeout_ms=timeout, output_json=output_json)


@gateway_app.command("call")
def gateway_call_cmd(
    method: str = typer.Argument(..., help="RPC method name."),
    params: str = typer.Option("{}", "--params", help="JSON params."),
    url: str = typer.Option("", "--url", help="Gateway WebSocket URL."),
    token: str | None = typer.Option(None, "--token", help="Auth token."),
    password: str | None = typer.Option(None, "--password", help="Auth password."),
    timeout: int = typer.Option(30000, "--timeout", help="Timeout in ms."),
    output_json: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    """Make a low-level RPC call to the gateway."""
    from pyclaw.cli.commands.gateway_cmd import gateway_call_command

    gateway_call_command(
        method=method,
        params_json=params,
        url=url,
        token=token,
        password=password,
        timeout_ms=timeout,
        output_json=output_json,
    )


@gateway_app.command("discover")
def gateway_discover_cmd(
    timeout: int = typer.Option(2000, "--timeout", help="Discovery timeout in ms."),
    output_json: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    """Discover gateways on the local network."""
    from pyclaw.cli.commands.gateway_cmd import gateway_discover_command

    gateway_discover_command(timeout_ms=timeout, output_json=output_json)


@app.command()
def ui(
    web: bool = typer.Option(False, "--web", help="Launch as web app instead of desktop."),
    port: int = typer.Option(8550, help="Port for web mode."),
) -> None:
    """Launch the pyclaw graphical interface."""
    from pyclaw.ui.app import run_app, run_web

    if web:
        typer.echo(f"Starting pyclaw web UI on port {port}")
        run_web(port=port)
    else:
        run_app()


@app.command()
def status(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
    deep: bool = typer.Option(False, "--deep", help="Probe gateway and channels."),
    all_info: bool = typer.Option(False, "--all", help="Show all status info."),
    usage: bool = typer.Option(False, "--usage", help="Show model/provider usage window."),
) -> None:
    """Show channel and gateway status."""
    from pyclaw.cli.commands.status import status_command

    status_command(output_json=output_json, deep=deep, all_info=all_info, usage=usage)


# ─── Config subcommands ──────────────────────────────────────────────────

config_app = typer.Typer(name="config", help="Manage configuration.", no_args_is_help=True)
app.add_typer(config_app)


@config_app.command("get")
def config_get(key: str = typer.Argument(..., help="Dotted config key (e.g. models.default).")) -> None:
    """Get a configuration value."""
    from pyclaw.cli.commands.config_cmd import config_get as _get

    _get(key)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Dotted config key."),
    value: str = typer.Argument(..., help="Value to set (JSON or string)."),
) -> None:
    """Set a configuration value."""
    from pyclaw.cli.commands.config_cmd import config_set as _set

    _set(key, value)


@config_app.command("list")
def config_list() -> None:
    """List all configuration values."""
    from pyclaw.cli.commands.config_cmd import config_list as _list

    _list()


@config_app.command("validate")
def config_validate_cmd() -> None:
    """Validate the configuration file."""
    from pyclaw.cli.commands.config_cmd import config_validate

    config_validate()


# ─── Agents subcommands ──────────────────────────────────────────────────

agents_app = typer.Typer(name="agents", help="Manage agents.", no_args_is_help=True)
app.add_typer(agents_app)


@agents_app.command("list")
def agents_list_cmd() -> None:
    """List all agents."""
    from pyclaw.cli.commands.agents_cmd import agents_list

    agents_list()


@agents_app.command("add")
def agents_add_cmd(
    agent_id: str = typer.Argument(..., help="Agent ID to create."),
    model: str | None = typer.Option(None, help="Default model for the agent."),
) -> None:
    """Create a new agent."""
    from pyclaw.cli.commands.agents_cmd import agents_add

    agents_add(agent_id, model)


@agents_app.command("remove")
def agents_remove_cmd(
    agent_id: str = typer.Argument(..., help="Agent ID to remove."),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation."),
) -> None:
    """Remove an agent."""
    from pyclaw.cli.commands.agents_cmd import agents_remove

    agents_remove(agent_id, force)


# ─── Channels subcommands ────────────────────────────────────────────────

channels_app = typer.Typer(name="channels", help="Manage channels.", no_args_is_help=True)
app.add_typer(channels_app)


@channels_app.command("list")
def channels_list_cmd() -> None:
    """List configured channels."""
    from pyclaw.cli.commands.channels_cmd import channels_list

    channels_list()


@channels_app.command("status")
def channels_status_cmd() -> None:
    """Show channel status."""
    from pyclaw.cli.commands.channels_cmd import channels_status

    channels_status()


@channels_app.command("add")
def channels_add_cmd(
    channel: str = typer.Option(..., "--channel", help="Channel type (e.g. telegram, discord)."),
    account: str = typer.Option("default", "--account", help="Account ID."),
    name: str = typer.Option("", "--name", help="Display name."),
) -> None:
    """Add channel configuration (basic)."""
    from pyclaw.cli.commands.channels_cmd import channels_add

    channels_add(channel=channel, account=account, name=name)


@channels_app.command("remove")
def channels_remove_cmd(
    channel: str = typer.Option(..., "--channel", help="Channel type."),
    account: str = typer.Option("default", "--account", help="Account ID."),
) -> None:
    """Remove channel configuration (basic)."""
    from pyclaw.cli.commands.channels_cmd import channels_remove

    channels_remove(channel=channel, account=account)


# ─── Auth subcommands ────────────────────────────────────────────────────

auth_app = typer.Typer(name="auth", help="Manage authentication.", no_args_is_help=True)
app.add_typer(auth_app)


@auth_app.command("login")
def auth_login_cmd(
    provider: str = typer.Option("openai", help="Provider name."),
    api_key: str | None = typer.Option(None, help="API key (prompted if not given)."),
    profile_id: str | None = typer.Option(None, help="Profile ID."),
    method: str = typer.Option("auto", help="Auth method: auto, api-key, oauth, device-code."),
) -> None:
    """Add or update an auth profile (API key, OAuth, or device-code)."""
    from pyclaw.cli.commands.auth_cmd import auth_login

    auth_login(provider, api_key, profile_id, method=method)


@auth_app.command("logout")
def auth_logout_cmd(
    profile_id: str | None = typer.Option(None, help="Profile ID to remove."),
    provider: str | None = typer.Option(None, help="Remove all profiles for this provider."),
) -> None:
    """Remove an auth profile."""
    from pyclaw.cli.commands.auth_cmd import auth_logout

    auth_logout(profile_id, provider)


@auth_app.command("status")
def auth_status_cmd() -> None:
    """Show auth profile status."""
    from pyclaw.cli.commands.auth_cmd import auth_status

    auth_status()


# ─── Models subcommands ──────────────────────────────────────────────────

models_app = typer.Typer(name="models", help="Manage models.", no_args_is_help=True)
app.add_typer(models_app)


@models_app.command("list")
def models_list_cmd(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List known models."""
    from pyclaw.cli.commands.models_cmd import models_list_command

    models_list_command(output_json=output_json)


@models_app.command("status")
def models_status_cmd(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
    probe: bool = typer.Option(False, "--probe", help="Run provider/model probe."),
) -> None:
    """Show model/auth status."""
    from pyclaw.cli.commands.models_cmd import models_status_command

    models_status_command(output_json=output_json, probe=probe)


@models_app.command("scan")
def models_scan_cmd(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Scan configured providers for model availability."""
    from pyclaw.cli.commands.models_cmd import models_scan_command

    models_scan_command(output_json=output_json)


@models_app.command("probe")
def models_probe_cmd(
    model: str = typer.Option(..., "--model", help="Model ID."),
    provider: str = typer.Option(..., "--provider", help="Provider ID."),
    api_key: str = typer.Option("", "--api-key", help="Provider API key override."),
    timeout: float = typer.Option(10.0, "--timeout", help="Probe timeout (seconds)."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Probe one model/provider pair."""
    from pyclaw.cli.commands.models_cmd import models_probe_command

    models_probe_command(
        model=model,
        provider=provider,
        api_key=api_key,
        timeout_s=timeout,
        output_json=output_json,
    )


@models_app.command("auth-overview")
def models_auth_overview_cmd(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show auth overview for provider credentials."""
    from pyclaw.cli.commands.models_cmd import models_auth_overview_command

    models_auth_overview_command(output_json=output_json)


@models_app.command("download")
def models_download_cmd(
    repo_id: str = typer.Argument(..., help="HuggingFace repo ID (e.g. Qwen/Qwen3-4B-GGUF)."),
    filename: str = typer.Option("", "--filename", help="Specific file to download."),
    backend: str = typer.Option("llamacpp", "--backend", help="Backend: llamacpp or mlx."),
    source: str = typer.Option("huggingface", "--source", help="Source: huggingface or modelscope."),
) -> None:
    """Download a local model from HuggingFace or ModelScope."""
    from pyclaw.cli.commands.local_models_cmd import local_models_download

    local_models_download(repo_id, filename=filename, backend=backend, source=source)


@models_app.command("local")
def models_local_cmd(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List downloaded local models."""
    from pyclaw.cli.commands.local_models_cmd import local_models_list

    local_models_list(output_json=output_json)


@models_app.command("delete-local")
def models_delete_local_cmd(
    model_id: str = typer.Argument(..., help="Model ID to delete."),
) -> None:
    """Delete a downloaded local model."""
    from pyclaw.cli.commands.local_models_cmd import local_models_delete

    local_models_delete(model_id)


@models_app.command("select")
def models_select_cmd(
    model_id: str = typer.Argument(..., help="Model ID to set as active."),
) -> None:
    """Set a local model as the active model for inference."""
    from pyclaw.cli.commands.local_models_cmd import local_models_select

    local_models_select(model_id)


# ─── Devices subcommands ─────────────────────────────────────────────────

devices_app = typer.Typer(name="devices", help="Manage paired devices.", no_args_is_help=True)
app.add_typer(devices_app)


@devices_app.command("list")
def devices_list_cmd() -> None:
    """List paired devices."""
    from pyclaw.cli.commands.devices_cmd import devices_list

    devices_list()


@devices_app.command("approve")
def devices_approve_cmd(
    channel: str = typer.Argument(..., help="Channel name (e.g. telegram, discord)."),
    code: str = typer.Argument(..., help="Pairing code to approve."),
) -> None:
    """Approve a pairing code."""
    from pyclaw.cli.commands.devices_cmd import devices_approve

    devices_approve(channel, code)


@devices_app.command("remove")
def devices_remove_cmd(
    channel: str = typer.Argument(..., help="Channel name."),
    sender_id: str = typer.Argument(..., help="Sender ID to remove."),
) -> None:
    """Remove a paired device."""
    from pyclaw.cli.commands.devices_cmd import devices_remove

    devices_remove(channel, sender_id)


# ─── Message subcommands ─────────────────────────────────────────────────

message_app = typer.Typer(name="message", help="Send messages.", no_args_is_help=True)
app.add_typer(message_app)


@message_app.command("send")
def message_send_cmd(
    text: str = typer.Argument(..., help="Message text to send."),
    channel: str = typer.Option("default", help="Target channel."),
    recipient: str = typer.Option("", help="Recipient ID."),
    gateway_url: str = typer.Option("ws://127.0.0.1:18789", help="Gateway WebSocket URL."),
    auth_token: str | None = typer.Option(None, envvar="PYCLAW_AUTH_TOKEN", help="Auth token."),
) -> None:
    """Send a message through the gateway."""
    from pyclaw.cli.commands.message_cmd import message_send

    message_send(text, channel, recipient, gateway_url, auth_token)


# ─── Pair shortcut ────────────────────────────────────────────────────────


@app.command()
def pair(
    action: str = typer.Argument(..., help="Action: 'approve'"),
    code: str = typer.Argument(..., help="Pairing code."),
    channel: str = typer.Option("", help="Channel name (auto-detect if empty)."),
) -> None:
    """Approve a pairing code (shortcut for 'devices approve')."""
    if action != "approve":
        typer.echo(f"Unknown action: {action}. Use 'approve'.", err=True)
        raise typer.Exit(1)
    from pyclaw.cli.commands.devices_cmd import devices_approve

    if not channel:
        typer.echo("Approving code across all channels...")
        from pyclaw.config.paths import resolve_credentials_dir
        from pyclaw.pairing.store import approve_pairing_code

        creds_dir = resolve_credentials_dir()
        if creds_dir.exists():
            for path in creds_dir.glob("*-pairing.json"):
                ch = path.stem.replace("-pairing", "")
                result = approve_pairing_code(ch, code)
                if result:
                    typer.echo(f"Approved: {result.display_name or result.sender_id} on {ch}")
                    return
        typer.echo("No matching pairing code found.", err=True)
        raise typer.Exit(1)
    devices_approve(channel, code)


# ─── Service subcommands ─────────────────────────────────────────────────

service_app = typer.Typer(name="service", help="Manage the gateway daemon/service.", no_args_is_help=True)
app.add_typer(service_app)


@service_app.command("install")
def service_install_cmd(
    label: str = typer.Option("ai.pyclaw.gateway", help="Service label."),
    port: int = typer.Option(18789, help="Gateway port."),
    bind: str = typer.Option("127.0.0.1", help="Bind address."),
) -> None:
    """Install gateway as a system service."""
    from pyclaw.cli.commands.service_cmd import service_install

    service_install(label, port, bind)


@service_app.command("uninstall")
def service_uninstall_cmd(
    label: str = typer.Option("ai.pyclaw.gateway", help="Service label."),
) -> None:
    """Uninstall the gateway service."""
    from pyclaw.cli.commands.service_cmd import service_uninstall

    service_uninstall(label)


@service_app.command("status")
def service_status_cmd(
    label: str = typer.Option("ai.pyclaw.gateway", help="Service label."),
) -> None:
    """Show gateway service status."""
    from pyclaw.cli.commands.service_cmd import service_status

    service_status(label)


@service_app.command("restart")
def service_restart_cmd(
    label: str = typer.Option("ai.pyclaw.gateway", help="Service label."),
) -> None:
    """Restart the gateway service."""
    from pyclaw.cli.commands.service_cmd import service_restart

    service_restart(label)


@service_app.command("stop")
def service_stop_cmd(
    label: str = typer.Option("ai.pyclaw.gateway", help="Service label."),
) -> None:
    """Stop the gateway service."""
    from pyclaw.cli.commands.service_cmd import service_stop

    service_stop(label)


# ─── Node Host command ───────────────────────────────────────────────────


@app.command()
def node(
    gateway_url: str = typer.Option("ws://127.0.0.1:18789/ws", help="Gateway WebSocket URL."),
    auth_token: str | None = typer.Option(None, envvar="PYCLAW_AUTH_TOKEN", help="Auth token."),
    node_id: str = typer.Option("", help="Node identifier (defaults to hostname)."),
) -> None:
    """Start a headless node host."""
    from pyclaw.cli.commands.node_cmd import node_run

    node_run(gateway_url, auth_token, node_id)


# ─── ACP subcommands ─────────────────────────────────────────────────────

acp_app = typer.Typer(name="acp", help="ACP bridge/server commands.", no_args_is_help=True)
app.add_typer(acp_app)


@acp_app.callback(invoke_without_command=True)
def acp_run(
    ctx: typer.Context,
    url: str = typer.Option("ws://127.0.0.1:18789/ws", "--url", help="Gateway URL."),
    token: str | None = typer.Option(None, "--token", help="Gateway auth token."),
    token_file: str | None = typer.Option(None, "--token-file", help="Read auth token from file."),
    password: str | None = typer.Option(None, "--password", help="Optional ACP password."),
    password_file: str | None = typer.Option(None, "--password-file", help="Read ACP password from file."),
    session: str = typer.Option("", "--session", help="Session mapping key."),
    session_label: str = typer.Option("", "--session-label", help="Session mapping label."),
    require_existing: bool = typer.Option(
        False,
        "--require-existing",
        "--require-existing-session",
        help="Require existing session mapping.",
    ),
    reset_session: bool = typer.Option(False, "--reset-session", help="Reset existing session mapping."),
    no_prefix_cwd: bool = typer.Option(False, "--no-prefix-cwd", help="Disable cwd prefixing."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose ACP logs."),
) -> None:
    """Run ACP server bridge (default `pyclaw acp`)."""
    if ctx.invoked_subcommand:
        return
    from pyclaw.cli.commands.acp_cmd import acp_run_command

    acp_run_command(
        url=url,
        token=token,
        token_file=token_file,
        password=password,
        password_file=password_file,
        session=session,
        session_label=session_label,
        require_existing=require_existing,
        reset_session=reset_session,
        no_prefix_cwd=no_prefix_cwd,
        verbose=verbose,
    )


@acp_app.command("client")
def acp_client_cmd(
    cwd: str = typer.Option("", "--cwd", help="Client working directory."),
    server: str = typer.Option("pyclaw", "--server", help="ACP server command."),
    server_args: list[str] | None = typer.Option(
        None,
        "--server-args",
        "--server-arg",
        help="Additional server args (repeatable).",
    ),
    url: str = typer.Option("ws://127.0.0.1:18789/ws", "--url", help="Gateway URL for spawned server."),
    token: str | None = typer.Option(None, "--token", help="Gateway auth token."),
    token_file: str | None = typer.Option(None, "--token-file", help="Read auth token from file."),
    password: str | None = typer.Option(None, "--password", help="Gateway password."),
    password_file: str | None = typer.Option(None, "--password-file", help="Read gateway password from file."),
    session: str = typer.Option("", "--session", help="Default ACP session key."),
    session_label: str = typer.Option("", "--session-label", help="Default ACP session label."),
    require_existing: bool = typer.Option(
        False,
        "--require-existing",
        "--require-existing-session",
        help="Require existing session mapping.",
    ),
    reset_session: bool = typer.Option(False, "--reset-session", help="Reset session before first prompt."),
    no_prefix_cwd: bool = typer.Option(False, "--no-prefix-cwd", help="Disable cwd prefixing."),
    timeout: int = typer.Option(30, "--timeout", help="Client request timeout in seconds."),
    server_verbose: bool = typer.Option(False, "--server-verbose", help="Verbose server process logs."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose client logs."),
) -> None:
    """Run ACP client bootstrap."""
    from pyclaw.cli.commands.acp_cmd import acp_client_command

    acp_client_command(
        cwd=cwd,
        server=server,
        server_args=server_args,
        url=url,
        token=token,
        token_file=token_file,
        password=password,
        password_file=password_file,
        session=session,
        session_label=session_label,
        require_existing=require_existing,
        reset_session=reset_session,
        no_prefix_cwd=no_prefix_cwd,
        timeout=timeout,
        server_verbose=server_verbose,
        verbose=verbose,
    )


# ─── Sessions/Logs/System/Browser/Health surface ────────────────────────

sessions_app = typer.Typer(name="sessions", help="Session management commands.")
app.add_typer(sessions_app)


@sessions_app.callback(invoke_without_command=True)
def sessions_root(
    ctx: typer.Context,
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose output."),
    store: str = typer.Option("", "--store", help="Specific session store path."),
    active: int | None = typer.Option(None, "--active", help="Only sessions active in last N minutes."),
    agent: str = typer.Option("", "--agent", help="Agent ID."),
    all_agents: bool = typer.Option(False, "--all-agents", help="Aggregate sessions from all agents."),
) -> None:
    """List stored conversation sessions."""
    if ctx.invoked_subcommand:
        return
    from pyclaw.cli.commands.sessions_cmd import sessions_command

    sessions_command(
        output_json=output_json,
        active_minutes=active,
        store=store,
        agent=agent,
        all_agents=all_agents,
        verbose=verbose,
    )


@sessions_app.command("cleanup")
def sessions_cleanup_cmd(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed without deleting."),
    enforce: bool = typer.Option(False, "--enforce", help="Also remove old sessions (>30 days)."),
    active_key: str = typer.Option("", "--active-key", help="Session key to exclude from cleanup."),
    store: str = typer.Option("", "--store", help="Specific session store path."),
    agent: str = typer.Option("", "--agent", help="Agent ID."),
    all_agents: bool = typer.Option(True, "--all-agents", help="Aggregate from all agents."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Clean up stale sessions (locks, empty files, old sessions)."""
    from pyclaw.cli.commands.sessions_cmd import sessions_cleanup_command

    sessions_cleanup_command(
        dry_run=dry_run,
        enforce=enforce,
        active_key=active_key,
        store=store,
        agent=agent,
        all_agents=all_agents,
        output_json=output_json,
    )


logs_app = typer.Typer(name="logs", help="Tail gateway logs.")
app.add_typer(logs_app)


@logs_app.callback(invoke_without_command=True)
def logs_root(
    ctx: typer.Context,
    follow: bool = typer.Option(False, "--follow", help="Follow new log lines."),
    limit: int = typer.Option(200, "--limit", help="Maximum log lines to show."),
    output_json: bool = typer.Option(False, "--json", help="Output as line-delimited JSON."),
    plain: bool = typer.Option(False, "--plain", help="Plain text output."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output."),
    local_time: bool = typer.Option(False, "--local-time", help="Use local timezone in JSON output."),
) -> None:
    """Tail gateway file logs."""
    if ctx.invoked_subcommand:
        return
    from pyclaw.cli.commands.logs_cmd import logs_command

    logs_command(
        follow=follow,
        limit=limit,
        output_json=output_json,
        plain=plain,
        no_color=no_color,
        local_time=local_time,
    )


system_app = typer.Typer(name="system", help="System-level commands.", no_args_is_help=True)
app.add_typer(system_app)


@system_app.command("event")
def system_event_cmd(
    text: str = typer.Option(..., "--text", help="System event text."),
    mode: str = typer.Option("next-heartbeat", "--mode", help="Delivery mode: now|next-heartbeat."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Enqueue a system event."""
    from pyclaw.cli.commands.system_cmd import system_event_command

    system_event_command(text=text, mode=mode, output_json=output_json)


heartbeat_app = typer.Typer(name="heartbeat", help="Heartbeat controls.", no_args_is_help=True)
system_app.add_typer(heartbeat_app)


@heartbeat_app.command("last")
def system_heartbeat_last_cmd(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show last heartbeat."""
    from pyclaw.cli.commands.system_cmd import system_heartbeat_last_command

    system_heartbeat_last_command(output_json=output_json)


@heartbeat_app.command("enable")
def system_heartbeat_enable_cmd(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Enable heartbeats."""
    from pyclaw.cli.commands.system_cmd import system_heartbeat_enable_command

    system_heartbeat_enable_command(output_json=output_json)


@heartbeat_app.command("disable")
def system_heartbeat_disable_cmd(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Disable heartbeats."""
    from pyclaw.cli.commands.system_cmd import system_heartbeat_disable_command

    system_heartbeat_disable_command(output_json=output_json)


@system_app.command("presence")
def system_presence_cmd(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List system presence entries."""
    from pyclaw.cli.commands.system_cmd import system_presence_command

    system_presence_command(output_json=output_json)


browser_app = typer.Typer(name="browser", help="Browser automation commands.", no_args_is_help=True)
app.add_typer(browser_app)


@browser_app.callback()
def browser_root(
    ctx: typer.Context,
    browser_profile: str = typer.Option("pyclaw", "--browser-profile", help="Browser profile name."),
    url: str = typer.Option("ws://127.0.0.1:18789", "--url", help="Gateway WebSocket URL."),
    token: str | None = typer.Option(None, "--token", envvar="PYCLAW_AUTH_TOKEN", help="Gateway auth token."),
    password: str | None = typer.Option(
        None, "--password", envvar="PYCLAW_GATEWAY_PASSWORD", help="Gateway auth password."
    ),
    timeout: int = typer.Option(10000, "--timeout", help="Gateway request timeout in ms."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Browser command root."""
    ctx.obj = {
        "browser_profile": browser_profile,
        "gateway_url": url,
        "token": token,
        "password": password,
        "timeout_ms": timeout,
        "output_json": output_json,
    }


@browser_app.command("status")
def browser_status_cmd(ctx: typer.Context) -> None:
    """Show browser status."""
    from pyclaw.cli.commands.browser_cmd import browser_status_command

    browser_status_command(
        profile=ctx.obj["browser_profile"],
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("start")
def browser_start_cmd(ctx: typer.Context) -> None:
    """Start browser profile."""
    from pyclaw.cli.commands.browser_cmd import browser_start_command

    browser_start_command(
        profile=ctx.obj["browser_profile"],
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("stop")
def browser_stop_cmd(ctx: typer.Context) -> None:
    """Stop browser profile."""
    from pyclaw.cli.commands.browser_cmd import browser_stop_command

    browser_stop_command(
        profile=ctx.obj["browser_profile"],
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("tabs")
def browser_tabs_cmd(ctx: typer.Context) -> None:
    """List tabs."""
    from pyclaw.cli.commands.browser_cmd import browser_tabs_command

    browser_tabs_command(
        profile=ctx.obj["browser_profile"],
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("open")
def browser_open_cmd(
    ctx: typer.Context,
    url: str = typer.Argument(..., help="URL to open."),
) -> None:
    """Open a URL in browser."""
    from pyclaw.cli.commands.browser_cmd import browser_open_command

    browser_open_command(
        url=url,
        profile=ctx.obj["browser_profile"],
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("navigate")
def browser_navigate_cmd(
    ctx: typer.Context,
    url: str = typer.Argument(..., help="URL to navigate."),
) -> None:
    """Navigate active tab to URL."""
    from pyclaw.cli.commands.browser_cmd import browser_navigate_command

    browser_navigate_command(
        url=url,
        profile=ctx.obj["browser_profile"],
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("click")
def browser_click_cmd(
    ctx: typer.Context,
    ref: str = typer.Argument(..., help="Element ref."),
) -> None:
    """Click by element ref."""
    from pyclaw.cli.commands.browser_cmd import browser_click_command

    browser_click_command(
        ref=ref,
        profile=ctx.obj["browser_profile"],
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("type")
def browser_type_cmd(
    ctx: typer.Context,
    ref: str = typer.Argument(..., help="Element ref."),
    text: str = typer.Argument(..., help="Input text."),
) -> None:
    """Type text into element."""
    from pyclaw.cli.commands.browser_cmd import browser_type_command

    browser_type_command(
        ref=ref,
        text=text,
        profile=ctx.obj["browser_profile"],
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("screenshot")
def browser_screenshot_cmd(
    ctx: typer.Context,
    out: str = typer.Option("browser-screenshot.png", "--out", help="Output path."),
) -> None:
    """Capture a browser screenshot via Gateway RPC."""
    from pyclaw.cli.commands.browser_cmd import browser_screenshot_command

    browser_screenshot_command(
        profile=ctx.obj["browser_profile"],
        output_json=ctx.obj["output_json"],
        out=out,
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("snapshot")
def browser_snapshot_cmd(ctx: typer.Context) -> None:
    """Capture page snapshot."""
    from pyclaw.cli.commands.browser_cmd import browser_snapshot_command

    browser_snapshot_command(
        profile=ctx.obj["browser_profile"],
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("profiles")
def browser_profiles_cmd(ctx: typer.Context) -> None:
    """List browser profiles."""
    from pyclaw.cli.commands.browser_cmd import browser_profiles_command

    browser_profiles_command(
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("create-profile")
def browser_create_profile_cmd(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Profile name."),
) -> None:
    """Create a new browser profile."""
    from pyclaw.cli.commands.browser_cmd import browser_create_profile_command

    browser_create_profile_command(
        name=name,
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("delete-profile")
def browser_delete_profile_cmd(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Profile name."),
) -> None:
    """Delete a browser profile."""
    from pyclaw.cli.commands.browser_cmd import browser_delete_profile_command

    browser_delete_profile_command(
        name=name,
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("focus")
def browser_focus_cmd(
    ctx: typer.Context,
    tab_id: str = typer.Argument(..., help="Tab ID to focus."),
) -> None:
    """Focus a specific tab."""
    from pyclaw.cli.commands.browser_cmd import browser_focus_command

    browser_focus_command(
        tab_id=tab_id,
        profile=ctx.obj["browser_profile"],
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("close")
def browser_close_cmd(
    ctx: typer.Context,
    tab_id: str = typer.Argument(..., help="Tab ID to close."),
) -> None:
    """Close a specific tab."""
    from pyclaw.cli.commands.browser_cmd import browser_close_command

    browser_close_command(
        tab_id=tab_id,
        profile=ctx.obj["browser_profile"],
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


@browser_app.command("evaluate")
def browser_evaluate_cmd(
    ctx: typer.Context,
    fn: str = typer.Option(..., "--fn", help="Expression to evaluate."),
) -> None:
    """Evaluate JS expression."""
    from pyclaw.cli.commands.browser_cmd import browser_evaluate_command

    browser_evaluate_command(
        fn=fn,
        profile=ctx.obj["browser_profile"],
        output_json=ctx.obj["output_json"],
        gateway_url=ctx.obj["gateway_url"],
        token=ctx.obj["token"],
        password=ctx.obj["password"],
        timeout_ms=ctx.obj["timeout_ms"],
    )


# ─── Security subcommands ────────────────────────────────────────────

security_app = typer.Typer(name="security", help="Security audit commands.", no_args_is_help=True)
app.add_typer(security_app)


@security_app.command("audit")
def security_audit_cmd(
    deep: bool = typer.Option(False, "--deep", help="Run deep filesystem/permission checks."),
    fix: bool = typer.Option(False, "--fix", help="Auto-fix fixable issues."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Audit configuration for security weaknesses."""
    from pyclaw.cli.commands.security_cmd import security_audit_command

    security_audit_command(deep=deep, fix=fix, output_json=output_json)


@app.command("health")
def health_cmd(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Quick health command alias for status. Exits 1 if gateway unreachable (for Docker HEALTHCHECK)."""
    from pyclaw.cli.commands.status import scan_status, status_command

    summary = scan_status(output_json=output_json, deep=True)
    status_command(output_json=output_json, deep=True, all_info=False)
    if not summary.gateway_running:
        raise typer.Exit(1)


# ─── MCP subcommands ─────────────────────────────────────────────────

mcp_app = typer.Typer(name="mcp", help="MCP (Model Context Protocol) server management.", no_args_is_help=True)
app.add_typer(mcp_app)


@mcp_app.command("status")
def mcp_status_cmd(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show status of configured MCP servers."""
    from pyclaw.cli.commands.mcp_cmd import mcp_status_command

    mcp_status_command(output_json=output_json)


@mcp_app.command("list-tools")
def mcp_list_tools_cmd(
    server: str | None = typer.Option(None, "--server", help="Filter by server name."),
) -> None:
    """List tools from connected MCP servers."""
    from pyclaw.cli.commands.mcp_cmd import mcp_list_tools_command

    mcp_list_tools_command(server=server)


# ─── Skills marketplace subcommands ──────────────────────────────────

skills_app = typer.Typer(name="skills", help="Skill discovery and management.", no_args_is_help=True)
app.add_typer(skills_app)


@skills_app.command("list")
def skills_list_cmd() -> None:
    """List installed skills."""
    from pyclaw.cli.commands.skills_cmd import skills_list_command

    skills_list_command()


@skills_app.command("search")
def skills_search_cmd(
    query: str = typer.Argument(..., help="Search query."),
) -> None:
    """Search for skills in the ClawHub marketplace."""
    from pyclaw.cli.commands.skills_cmd import skills_search_command

    skills_search_command(query=query)


@skills_app.command("install")
def skills_install_cmd(
    name: str = typer.Argument(..., help="Skill name or URL to install."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing skill."),
) -> None:
    """Install a skill from ClawHub or a URL."""
    from pyclaw.cli.commands.skills_cmd import skills_install_command

    skills_install_command(name=name, force=force)


@skills_app.command("remove")
def skills_remove_cmd(
    name: str = typer.Argument(..., help="Skill name to remove."),
) -> None:
    """Remove an installed skill."""
    from pyclaw.cli.commands.skills_cmd import skills_remove_command

    skills_remove_command(name=name)


# ─── Workspace subcommands ───────────────────────────────────────────

workspace_app = typer.Typer(name="workspace", help="Workspace template management.", no_args_is_help=True)
app.add_typer(workspace_app)


@workspace_app.command("sync")
def workspace_sync_cmd(
    force: bool = typer.Option(False, "--force", help="Overwrite modified files."),
) -> None:
    """Sync workspace templates (create missing files)."""
    from pyclaw.cli.commands.workspace_cmd import workspace_sync_command

    workspace_sync_command(force=force)


@workspace_app.command("diff")
def workspace_diff_cmd() -> None:
    """Show differences between workspace files and templates."""
    from pyclaw.cli.commands.workspace_cmd import workspace_diff_command

    workspace_diff_command()


# ─── Backup subcommands ──────────────────────────────────────────────

from pyclaw.cli.commands.backup_cmd import backup_app

app.add_typer(backup_app)


# ─── Uninstall command ───────────────────────────────────────────────


@app.command()
def uninstall(
    purge: bool = typer.Option(False, "--purge", help="Remove all data and config (irreversible)."),
) -> None:
    """Uninstall pyclaw. With --purge, removes all data and config."""
    import shutil

    from pyclaw.config.paths import resolve_config_path, resolve_state_dir

    if purge:
        for d in (resolve_config_path().parent, resolve_state_dir()):
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
                typer.echo(f"Removed: {d}")
        typer.echo("All pyclaw data and config purged.")
    else:
        typer.echo("To uninstall openclaw-py:")
        typer.echo("  pipx uninstall openclaw-py")
        typer.echo("  # or: pip uninstall openclaw-py")
        typer.echo("")
        typer.echo("Or use the one-line uninstaller:")
        typer.echo(
            "  curl -fsSL https://raw.githubusercontent.com/chensaics/openclaw-py/master/scripts/uninstall.sh | bash"
        )
        typer.echo("")
        typer.echo("To also remove data and config, add --purge")
