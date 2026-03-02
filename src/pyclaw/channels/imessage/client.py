"""iMessage RPC client — JSON-RPC 2.0 over stdio to ``imsg rpc``.

Spawns ``imsg rpc`` as a child process and communicates line-by-line.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

NotificationHandler = Callable[[str, dict[str, Any]], Awaitable[None] | None]


@dataclass
class RpcResponse:
    id: int
    result: Any = None
    error: dict[str, Any] | None = None


class IMessageRpcClient:
    """Manages a child ``imsg rpc`` process with JSON-RPC 2.0 over stdio."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path
        self._process: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[RpcResponse]] = {}
        self._on_notification: NotificationHandler | None = None
        self._reader_task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def start(self) -> None:
        cmd = ["imsg", "rpc"]
        if self._db_path:
            cmd.extend(["--db", self._db_path])

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader_task = asyncio.ensure_future(self._read_loop())

    async def stop(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.kill()
            self._process = None

    def on_notification(self, handler: NotificationHandler) -> None:
        self._on_notification = handler

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> Any:
        """Send a JSON-RPC request and wait for the response."""
        if not self._process or not self._process.stdin:
            raise RuntimeError("RPC client not started")

        req_id = self._next_id
        self._next_id += 1

        payload = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params:
            payload["params"] = params

        line = json.dumps(payload) + "\n"
        self._process.stdin.write(line.encode("utf-8"))
        await self._process.stdin.drain()

        future: asyncio.Future[RpcResponse] = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError:
            self._pending.pop(req_id, None)
            raise TimeoutError(f"RPC request {method} timed out after {timeout}s")

        if response.error:
            raise RuntimeError(f"RPC error: {response.error}")
        return response.result

    async def _read_loop(self) -> None:
        if not self._process or not self._process.stdout:
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

                if "id" in data and data["id"] in self._pending:
                    future = self._pending.pop(data["id"])
                    future.set_result(
                        RpcResponse(
                            id=data["id"],
                            result=data.get("result"),
                            error=data.get("error"),
                        )
                    )
                elif "method" in data and "id" not in data:
                    # Notification
                    if self._on_notification:
                        method = data["method"]
                        params = data.get("params", {})
                        try:
                            result = self._on_notification(method, params)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception:
                            logger.exception("Notification handler error")
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("RPC read loop error")


async def create_imessage_rpc_client(
    db_path: str | None = None,
) -> IMessageRpcClient:
    """Create and start an iMessage RPC client."""
    client = IMessageRpcClient(db_path=db_path)
    await client.start()
    return client


def probe_imessage() -> bool:
    """Check if ``imsg`` is available on the system."""
    return shutil.which("imsg") is not None
