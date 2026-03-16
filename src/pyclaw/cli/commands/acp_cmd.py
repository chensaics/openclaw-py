"""ACP CLI command surface (`pyclaw acp`, `pyclaw acp client`)."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import typer

from pyclaw.constants.env import GATEWAY_PASSWORD_ENV_VARS, GATEWAY_TOKEN_FALLBACK_ENV_VARS
from pyclaw.constants.runtime import DEFAULT_GATEWAY_WS_URL_PATH


def _read_secret_file(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path).expanduser()
    if not p.exists():
        raise typer.BadParameter(f"File not found: {path}")
    return p.read_text(encoding="utf-8").strip()


def acp_run_command(
    *,
    url: str = DEFAULT_GATEWAY_WS_URL_PATH,
    token: str | None = None,
    token_file: str | None = None,
    password: str | None = None,
    password_file: str | None = None,
    session: str = "",
    session_label: str = "",
    require_existing: bool = False,
    reset_session: bool = False,
    no_prefix_cwd: bool = False,
    verbose: bool = False,
) -> None:
    from pyclaw.acp.server import serve_acp_gateway

    resolved_token = token or _read_secret_file(token_file)
    resolved_password = password or _read_secret_file(password_file)
    if not resolved_token:
        resolved_token = next(
            (os.environ.get(name) for name in GATEWAY_TOKEN_FALLBACK_ENV_VARS if os.environ.get(name)),
            None,
        )
    if not resolved_password:
        resolved_password = next(
            (os.environ.get(name) for name in GATEWAY_PASSWORD_ENV_VARS if os.environ.get(name)),
            None,
        )

    asyncio.run(
        serve_acp_gateway(
            gateway_url=url,
            auth_token=resolved_token,
            auth_password=resolved_password,
            default_session_key=session,
            default_session_label=session_label,
            require_existing_session=require_existing,
            reset_session_default=reset_session,
            prefix_cwd=not no_prefix_cwd,
            verbose=verbose,
        )
    )


def acp_client_command(
    *,
    cwd: str = "",
    server: str = "pyclaw",
    server_args: list[str] | None = None,
    url: str = DEFAULT_GATEWAY_WS_URL_PATH,
    token: str | None = None,
    token_file: str | None = None,
    password: str | None = None,
    password_file: str | None = None,
    session: str = "",
    session_label: str = "",
    require_existing: bool = False,
    reset_session: bool = False,
    no_prefix_cwd: bool = False,
    timeout: int = 30,
    server_verbose: bool = False,
    verbose: bool = False,
) -> None:
    from pyclaw.acp.client import create_acp_client

    resolved_token = token or _read_secret_file(token_file)
    resolved_password = password or _read_secret_file(password_file)
    if not resolved_token:
        resolved_token = next(
            (os.environ.get(name) for name in GATEWAY_TOKEN_FALLBACK_ENV_VARS if os.environ.get(name)),
            None,
        )
    if not resolved_password:
        resolved_password = next(
            (os.environ.get(name) for name in GATEWAY_PASSWORD_ENV_VARS if os.environ.get(name)),
            None,
        )

    async def _run() -> None:
        client = await create_acp_client(
            cwd=cwd,
            server=server,
            server_args=server_args,
            server_verbose=server_verbose,
            verbose=verbose,
            request_timeout_s=float(timeout),
            gateway_url=url,
            auth_token=resolved_token,
            auth_password=resolved_password,
            session=session,
            session_label=session_label,
            require_existing_session=require_existing,
            reset_session=reset_session,
            no_prefix_cwd=no_prefix_cwd,
        )
        try:
            result = await client.request("initialize", {})
            typer.echo(json.dumps(result, ensure_ascii=False))
        finally:
            await client.close()

    asyncio.run(_run())
