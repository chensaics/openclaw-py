"""MCP stdio transport — communicate with a local MCP server via stdin/stdout."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from typing import Any

from pyclaw.mcp.types import JsonRpcRequest, JsonRpcResponse

logger = logging.getLogger(__name__)


class StdioTransport:
    """Manages a child process MCP server communicating over JSON-RPC via stdio."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._command = command
        self._args = args or []
        self._env = env or {}
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending: dict[int | str, asyncio.Future[JsonRpcResponse]] = {}
        self._reader_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        cmd_path = shutil.which(self._command) or self._command
        merged_env = {**os.environ, **self._env}

        self._process = await asyncio.create_subprocess_exec(
            cmd_path,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
        )
        self._reader_task = asyncio.create_task(self._read_loop())
        logger.info("MCP stdio: started %s %s (pid=%s)", self._command, self._args, self._process.pid)

    async def disconnect(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None

        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except (TimeoutError, ProcessLookupError):
                self._process.kill()
            self._process = None

        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

    async def send(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._request_id += 1
        req = JsonRpcRequest(method=method, params=params, id=self._request_id)
        return await self._send_request(req)

    async def _send_request(self, req: JsonRpcRequest) -> Any:
        if not self._process or not self._process.stdin:
            raise RuntimeError("MCP stdio transport not connected")

        fut: asyncio.Future[JsonRpcResponse] = asyncio.get_event_loop().create_future()
        assert req.id is not None
        self._pending[req.id] = fut

        payload = json.dumps(req.to_dict()) + "\n"
        self._process.stdin.write(payload.encode("utf-8"))
        await self._process.stdin.drain()

        resp = await fut
        if resp.is_error:
            err = resp.error or {}
            raise RuntimeError(f"MCP error {err.get('code', '?')}: {err.get('message', 'unknown')}")
        return resp.result

    async def _read_loop(self) -> None:
        assert self._process and self._process.stdout
        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    break
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                resp = JsonRpcResponse.from_dict(data)
                fut = self._pending.pop(resp.id, None) if resp.id is not None else None
                if fut and not fut.done():
                    fut.set_result(resp)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("MCP stdio reader error")

    @property
    def is_connected(self) -> bool:
        return self._process is not None and self._process.returncode is None
