"""ACP client — spawn ACP server process and communicate via NDJSON."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import sys
from typing import Any

from pyclaw.constants.runtime import DEFAULT_GATEWAY_WS_URL_PATH

logger = logging.getLogger(__name__)


class AcpClientHandle:
    """Handle to a running ACP server process."""

    def __init__(
        self,
        process: asyncio.subprocess.Process,
        *,
        request_timeout_s: float = 30.0,
        verbose: bool = False,
    ) -> None:
        self._process = process
        self._request_timeout_s = request_timeout_s
        self._verbose = verbose
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._reader_task = asyncio.ensure_future(self._read_loop())
        self._stderr_task = asyncio.ensure_future(self._stderr_loop())

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        req_id = self._next_id
        self._next_id += 1

        payload = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params:
            payload["params"] = params

        if self._process.stdin:
            line = json.dumps(payload) + "\n"
            self._process.stdin.write(line.encode("utf-8"))
            await self._process.stdin.drain()

        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future
        return await asyncio.wait_for(future, timeout=self._request_timeout_s)

    async def close(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
        if self._stderr_task:
            self._stderr_task.cancel()
        self._process.terminate()
        await self._process.wait()

    async def _read_loop(self) -> None:
        if not self._process.stdout:
            return
        try:
            async for line_bytes in self._process.stdout:
                line = line_bytes.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                req_id = data.get("id")
                if req_id and req_id in self._pending:
                    future = self._pending.pop(req_id)
                    if data.get("error"):
                        future.set_exception(RuntimeError(str(data["error"])))
                    else:
                        future.set_result(data.get("result"))
        except asyncio.CancelledError:
            pass

    async def _stderr_loop(self) -> None:
        if not self._process.stderr:
            return
        try:
            async for line_bytes in self._process.stderr:
                if self._verbose:
                    line = line_bytes.decode("utf-8", errors="ignore").rstrip("\n")
                    if line:
                        logger.info("[acp-server] %s", line)
        except asyncio.CancelledError:
            pass


async def create_acp_client(
    *,
    cwd: str = "",
    server: str = "pyclaw",
    server_args: list[str] | None = None,
    server_verbose: bool = False,
    verbose: bool = False,
    request_timeout_s: float = 30.0,
    gateway_url: str = DEFAULT_GATEWAY_WS_URL_PATH,
    auth_token: str | None = None,
    auth_password: str | None = None,
    session: str = "",
    session_label: str = "",
    require_existing_session: bool = False,
    reset_session: bool = False,
    no_prefix_cwd: bool = False,
) -> AcpClientHandle:
    """Spawn an ACP server process and return a client handle."""
    cmd = _build_server_command(
        server=server,
        server_args=server_args or [],
        gateway_url=gateway_url,
        auth_token=auth_token,
        auth_password=auth_password,
        session=session,
        session_label=session_label,
        require_existing_session=require_existing_session,
        reset_session=reset_session,
        no_prefix_cwd=no_prefix_cwd,
        server_verbose=server_verbose,
    )

    if verbose:
        logger.info("Starting ACP server: %s", shlex.join(cmd))

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd or None,
        env=dict(os.environ),
    )

    client = AcpClientHandle(
        process,
        request_timeout_s=request_timeout_s,
        verbose=verbose or server_verbose,
    )
    await client.start()
    return client


def _build_server_command(
    *,
    server: str,
    server_args: list[str],
    gateway_url: str,
    auth_token: str | None,
    auth_password: str | None,
    session: str,
    session_label: str,
    require_existing_session: bool,
    reset_session: bool,
    no_prefix_cwd: bool,
    server_verbose: bool,
) -> list[str]:
    if server in {"pyclaw"}:
        cmd = [sys.executable, "-m", "pyclaw.acp.server", "--gateway-url", gateway_url]
        if auth_token:
            cmd.extend(["--auth-token", auth_token])
        if auth_password:
            cmd.extend(["--auth-password", auth_password])
        if session:
            cmd.extend(["--session", session])
        if session_label:
            cmd.extend(["--session-label", session_label])
        if require_existing_session:
            cmd.append("--require-existing-session")
        if reset_session:
            cmd.append("--reset-session")
        if no_prefix_cwd:
            cmd.append("--no-prefix-cwd")
        if server_verbose:
            cmd.append("--verbose")
        return cmd

    return [server, *server_args]
