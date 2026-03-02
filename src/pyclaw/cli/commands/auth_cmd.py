"""CLI auth subcommands — login, logout, status."""

from __future__ import annotations

import typer

from pyclaw.terminal.palette import PALETTE
from pyclaw.terminal.table import TableColumn, render_table

_DEVICE_CODE_PROVIDERS = {"github-copilot"}
_OAUTH_PROVIDERS = {"openai-codex", "minimax-portal", "qwen-portal"}
_API_KEY_PROVIDERS = {"azure-openai"}


def auth_login(
    provider: str = "openai",
    api_key: str | None = None,
    profile_id: str | None = None,
    *,
    method: str = "auto",
) -> None:
    """Add or update an auth profile (API key, OAuth, or device-code)."""
    p = PALETTE

    effective_method = method
    if effective_method == "auto":
        if provider in _DEVICE_CODE_PROVIDERS:
            effective_method = "device-code"
        elif provider in _OAUTH_PROVIDERS:
            effective_method = "oauth"
        else:
            effective_method = "api-key"

    if effective_method == "device-code":
        _login_device_code(provider, profile_id)
    elif effective_method == "oauth":
        _login_oauth(provider, profile_id)
    else:
        _login_api_key(provider, api_key, profile_id)


def _login_api_key(
    provider: str,
    api_key: str | None,
    profile_id: str | None,
) -> None:
    from pyclaw.agents.auth_profiles import (
        ApiKeyCredential,
        load_auth_profile_store,
        save_auth_profile_store,
        upsert_auth_profile,
    )
    from pyclaw.config.secrets import normalize_secret_input

    p = PALETTE

    if not api_key:
        api_key = typer.prompt("API Key", hide_input=True)

    if not api_key:
        typer.echo(f"{p.error}API key is required.{p.reset}")
        raise typer.Exit(1)

    api_key = normalize_secret_input(api_key)
    pid = profile_id or f"{provider}-default"

    store = load_auth_profile_store()
    cred = ApiKeyCredential(provider=provider, key=api_key)
    upsert_auth_profile(store, pid, cred)
    save_auth_profile_store(store)

    masked = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    typer.echo(f"{p.success}Saved auth profile '{pid}' for {provider} ({masked}).{p.reset}")


def _login_device_code(provider: str, profile_id: str | None) -> None:
    """Run device-code OAuth flow (e.g. GitHub Copilot)."""
    import asyncio

    from pyclaw.agents.auth_profiles import (
        ApiKeyCredential,
        load_auth_profile_store,
        save_auth_profile_store,
        upsert_auth_profile,
    )

    p = PALETTE
    pid = profile_id or f"{provider}-default"

    typer.echo(f"{p.info}Starting device-code login for {provider}...{p.reset}")

    tokens = asyncio.run(_run_device_code_flow(provider))
    if tokens is None:
        typer.echo(f"{p.error}Login failed or timed out.{p.reset}")
        raise typer.Exit(1)

    store = load_auth_profile_store()
    cred = ApiKeyCredential(provider=provider, key=tokens.access_token)
    upsert_auth_profile(store, pid, cred)
    save_auth_profile_store(store)

    typer.echo(f"{p.success}Saved auth profile '{pid}' for {provider}.{p.reset}")


async def _run_device_code_flow(provider: str) -> object | None:
    import httpx

    from pyclaw.agents.providers.oauth_providers import CopilotDeviceFlow

    flow = CopilotDeviceFlow()
    req_body = flow.build_device_code_request()

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            flow.device_code_url,
            data=req_body,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        dc = flow.parse_device_code_response(resp.json())

    from pyclaw.terminal.palette import PALETTE

    p = PALETTE
    typer.echo(f"\n  {p.info}Open: {dc.verification_uri}{p.reset}")
    typer.echo(f"  {p.info}Enter code: {dc.user_code}{p.reset}\n")
    typer.echo("  Waiting for authorization...")

    import asyncio

    deadline = asyncio.get_event_loop().time() + dc.expires_in
    interval = dc.interval

    async with httpx.AsyncClient(timeout=30.0) as client:
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(interval)
            poll_body = flow.build_token_poll_request()
            resp = await client.post(
                flow.token_url,
                data=poll_body,
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                continue
            tokens = flow.parse_token_response(resp.json())
            if tokens is not None:
                return tokens

    return None


def _login_oauth(provider: str, profile_id: str | None) -> None:
    """Run browser-based OAuth flow with local redirect server."""
    p = PALETTE
    typer.echo(f"{p.warn}OAuth browser flow for '{provider}' is not yet fully automated.{p.reset}")
    typer.echo("Please use API key login or contact support for OAuth setup.")
    typer.echo(f"  pyclaw auth login --provider {provider} --method api-key")


def auth_logout(profile_id: str | None = None, provider: str | None = None) -> None:
    """Remove an auth profile."""
    from pyclaw.agents.auth_profiles import (
        load_auth_profile_store,
        save_auth_profile_store,
    )

    p = PALETTE
    store = load_auth_profile_store()

    if profile_id:
        if profile_id in store.profiles:
            del store.profiles[profile_id]
            save_auth_profile_store(store)
            typer.echo(f"{p.success}Removed profile '{profile_id}'.{p.reset}")
        else:
            typer.echo(f"{p.warn}Profile '{profile_id}' not found.{p.reset}")
    elif provider:
        removed = [pid for pid, cred in store.profiles.items() if cred.provider == provider]
        for pid in removed:
            del store.profiles[pid]
        if removed:
            save_auth_profile_store(store)
            typer.echo(f"{p.success}Removed {len(removed)} profile(s) for {provider}.{p.reset}")
        else:
            typer.echo(f"{p.warn}No profiles found for {provider}.{p.reset}")
    else:
        typer.echo(f"{p.error}Specify --profile-id or --provider.{p.reset}")
        raise typer.Exit(1)


def auth_status() -> None:
    """Show auth profile status."""
    from pyclaw.agents.auth_profiles import (
        is_profile_in_cooldown,
        load_auth_profile_store,
    )
    from pyclaw.agents.auth_profiles.profiles import resolve_auth_profile_display_label

    p = PALETTE
    store = load_auth_profile_store()

    if not store.profiles:
        typer.echo(f"  {p.muted}No auth profiles configured.{p.reset}")
        typer.echo("  Run 'pyclaw auth login --provider <provider>' to add one.")
        return

    rows: list[dict[str, str]] = []
    for pid, cred in store.profiles.items():
        label = resolve_auth_profile_display_label(pid, cred)
        in_cooldown = is_profile_in_cooldown(store, pid)
        stats = store.usage_stats.get(pid)

        status = "active"
        if stats and stats.disabled_until == "permanent":
            status = f"disabled ({stats.disabled_reason})"
        elif in_cooldown:
            status = "cooldown"

        rows.append(
            {
                "id": pid,
                "provider": cred.provider,
                "type": cred.type,
                "label": label,
                "status": status,
            }
        )

    cols = [
        TableColumn(key="id", header="Profile ID", min_width=10),
        TableColumn(key="provider", header="Provider", min_width=8),
        TableColumn(key="type", header="Type", min_width=6),
        TableColumn(key="label", header="Label", min_width=10, flex=True),
        TableColumn(key="status", header="Status", min_width=8),
    ]
    typer.echo(f"\n{p.info}Auth Profiles:{p.reset}")
    typer.echo(render_table(cols, rows))
