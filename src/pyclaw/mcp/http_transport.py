"""MCP HTTP transport — communicate with a remote MCP server via HTTP/SSE."""

from __future__ import annotations

import json
import logging
from typing import Any

from pyclaw.mcp.types import JsonRpcRequest, JsonRpcResponse

logger = logging.getLogger(__name__)


class HttpTransport:
    """Communicate with a remote MCP server over HTTP (JSON-RPC POST)."""

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._headers = headers or {}
        self._request_id = 0
        self._client: Any = None

    async def connect(self) -> None:
        import httpx

        self._client = httpx.AsyncClient(
            headers={
                "Content-Type": "application/json",
                **self._headers,
            },
            timeout=60.0,
        )
        logger.info("MCP HTTP: connected to %s", self._url)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._request_id += 1
        req = JsonRpcRequest(method=method, params=params, id=self._request_id)
        return await self._send_request(req)

    async def _send_request(self, req: JsonRpcRequest) -> Any:
        if not self._client:
            raise RuntimeError("MCP HTTP transport not connected")

        resp = await self._client.post(self._url, json=req.to_dict())
        resp.raise_for_status()

        data = resp.json()

        if isinstance(data, list):
            data = data[0] if data else {}

        rpc_resp = JsonRpcResponse.from_dict(data)
        if rpc_resp.is_error:
            err = rpc_resp.error or {}
            raise RuntimeError(f"MCP error {err.get('code', '?')}: {err.get('message', 'unknown')}")
        return rpc_resp.result

    @property
    def is_connected(self) -> bool:
        return self._client is not None
