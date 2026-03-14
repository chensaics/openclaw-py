"""Gateway WebSocket client — connects Flet UI to the pyclaw gateway.

Implements the v3 WebSocket protocol with automatic reconnection,
heartbeat keep-alive, and event listener registration.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_URL = "ws://127.0.0.1:18789/"
_HEARTBEAT_INTERVAL = 30.0
_RECONNECT_BASE_DELAY = 1.0
_RECONNECT_MAX_DELAY = 30.0


class GatewayError(Exception):
    """Raised when a gateway RPC call returns an error."""

    def __init__(self, code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


class GatewayClient:
    """Async WebSocket client for the pyclaw gateway v3 protocol."""

    def __init__(
        self,
        url: str = _DEFAULT_URL,
        auth_token: str | None = None,
        client_name: str = "pyclaw-flet-ui",
    ) -> None:
        self._url = url
        self._auth_token = auth_token
        self._client_name = client_name

        self._ws: Any = None
        self._connected = False
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._event_listeners: dict[str, list[Callable[..., Any]]] = {}
        self._global_listeners: list[Callable[..., Any]] = []

        self._recv_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._should_reconnect = True
        self._reconnect_delay = _RECONNECT_BASE_DELAY

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Connect to the gateway and perform the v3 handshake."""
        try:
            import websockets
        except ImportError:
            raise RuntimeError("websockets required: pip install websockets")

        try:
            self._ws = await websockets.connect(self._url)
        except Exception as exc:
            logger.warning("Failed to connect to gateway: %s", exc)
            self._schedule_reconnect()
            return

        self._recv_task = asyncio.create_task(self._recv_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        auth_params: dict[str, Any] = {}
        if self._auth_token:
            auth_params["auth"] = {"token": self._auth_token}

        try:
            result = await self.call(
                "connect",
                {
                    "minProtocol": 1,
                    "maxProtocol": 3,
                    "clientName": self._client_name,
                    **auth_params,
                },
            )
            self._connected = True
            self._reconnect_delay = _RECONNECT_BASE_DELAY
            logger.info("Connected to gateway (protocol=%s)", result.get("protocol"))
        except Exception as exc:
            logger.error("Handshake failed: %s", exc)
            await self.disconnect()
            raise

    async def disconnect(self) -> None:
        """Disconnect from the gateway."""
        self._should_reconnect = False
        self._connected = False
        for task in (self._recv_task, self._heartbeat_task, self._reconnect_task):
            if task and not task.done():
                task.cancel()
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()
        self.clear_all_listeners()

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Send an RPC request and wait for the response."""
        if not self._ws:
            raise GatewayError("not_connected", "Not connected to gateway")

        req_id = uuid.uuid4().hex[:12]
        frame: dict[str, Any] = {"type": "req", "id": req_id, "method": method}
        if params:
            frame["params"] = params

        fut: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut

        try:
            await self._ws.send(json.dumps(frame))
            result = await asyncio.wait_for(fut, timeout=timeout)
        except TimeoutError:
            self._pending.pop(req_id, None)
            raise GatewayError("timeout", f"RPC call '{method}' timed out")
        except Exception:
            self._pending.pop(req_id, None)
            raise

        return result

    def on_event(self, event_name: str, callback: Callable[..., Any]) -> None:
        """Register a listener for a specific event type."""
        if event_name not in self._event_listeners:
            self._event_listeners[event_name] = []
        self._event_listeners[event_name].append(callback)

    def off_event(self, event_name: str, callback: Callable[..., Any]) -> None:
        """Remove an event listener."""
        listeners = self._event_listeners.get(event_name, [])
        if callback in listeners:
            listeners.remove(callback)

    def on_any_event(self, callback: Callable[..., Any]) -> None:
        """Register a listener for all events."""
        self._global_listeners.append(callback)

    def clear_all_listeners(self) -> None:
        self._event_listeners.clear()
        self._global_listeners.clear()

    async def _recv_loop(self) -> None:
        """Background loop that reads and dispatches incoming frames."""
        try:
            async for raw in self._ws:
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue

                frame_type = data.get("type")
                if frame_type == "res":
                    self._handle_response(data)
                elif frame_type == "event":
                    await self._handle_event(data)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("WebSocket recv error: %s", exc)
        finally:
            self._connected = False
            if self._should_reconnect:
                self._schedule_reconnect()

    def _handle_response(self, data: dict[str, Any]) -> None:
        req_id = data.get("id", "")
        fut = self._pending.pop(req_id, None)
        if not fut or fut.done():
            return

        if data.get("ok"):
            fut.set_result(data.get("payload") or {})
        else:
            err = data.get("error", {})
            fut.set_exception(
                GatewayError(
                    code=err.get("code", "unknown"),
                    message=err.get("message", "Unknown error"),
                    details=err.get("details"),
                )
            )

    async def _handle_event(self, data: dict[str, Any]) -> None:
        event_name = data.get("event", "")
        payload = data.get("payload")

        for cb in self._global_listeners:
            try:
                result = cb(event_name, payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception("Error in global event listener")

        for cb in self._event_listeners.get(event_name, []):
            try:
                result = cb(payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception("Error in event listener for %s", event_name)

    async def _heartbeat_loop(self) -> None:
        """Send periodic health checks to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(_HEARTBEAT_INTERVAL)
                if self._connected and self._ws:
                    try:
                        await self.call("health", timeout=10.0)
                    except Exception:
                        pass
        except asyncio.CancelledError:
            return

    def _schedule_reconnect(self) -> None:
        if not self._should_reconnect:
            return
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        while self._should_reconnect and not self._connected:
            logger.info("Reconnecting in %.1fs ...", self._reconnect_delay)
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 2, _RECONNECT_MAX_DELAY)
            try:
                await self.connect()
                if self._connected:
                    return
            except Exception:
                pass


# Convenience helpers for common RPC patterns


async def chat_send(
    client: GatewayClient,
    message: str,
    *,
    on_delta: Callable[[str], Any] | None = None,
    on_tool_start: Callable[[str, str], Any] | None = None,
    on_tool_end: Callable[[str, str | None, str | None], Any] | None = None,
    on_error: Callable[[str], Any] | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Send a chat message and stream the response via event callbacks.

    Returns the final RPC response payload.
    """
    asyncio.Event()

    async def _on_delta(payload: Any) -> None:
        if on_delta and payload and payload.get("delta"):
            result = on_delta(payload["delta"])
            if asyncio.iscoroutine(result):
                await result

    async def _on_tool_start(payload: Any) -> None:
        if on_tool_start and payload:
            result = on_tool_start(payload.get("name", ""), payload.get("toolCallId", ""))
            if asyncio.iscoroutine(result):
                await result

    async def _on_tool_end(payload: Any) -> None:
        if on_tool_end and payload:
            result_val = None
            result_data = payload.get("result")
            if isinstance(result_data, dict):
                content = result_data.get("content")
                result_val = str(content) if content else None
            elif isinstance(result_data, str):
                result_val = result_data
            result = on_tool_end(
                payload.get("name", ""),
                result_val,
                payload.get("error"),
            )
            if asyncio.iscoroutine(result):
                await result

    async def _on_error(payload: Any) -> None:
        if on_error and payload:
            result = on_error(payload.get("error", "unknown error"))
            if asyncio.iscoroutine(result):
                await result

    client.on_event("chat.message_update", _on_delta)
    client.on_event("chat.tool_start", _on_tool_start)
    client.on_event("chat.tool_end", _on_tool_end)
    client.on_event("chat.error", _on_error)

    try:
        params: dict[str, Any] = {"message": message}
        if agent_id:
            params["agentId"] = agent_id
        if session_id:
            params["sessionId"] = session_id
        if provider:
            params["provider"] = provider
        if model:
            params["model"] = model
        if api_key:
            params["apiKey"] = api_key
        if system_prompt:
            params["systemPrompt"] = system_prompt

        result = await client.call("chat.send", params, timeout=300.0)
        return result
    finally:
        client.off_event("chat.message_update", _on_delta)
        client.off_event("chat.tool_start", _on_tool_start)
        client.off_event("chat.tool_end", _on_tool_end)
        client.off_event("chat.error", _on_error)
