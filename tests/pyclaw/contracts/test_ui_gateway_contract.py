from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from pyclaw.ui.gateway_client import chat_send


class _FakeGatewayClient:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., Any]]] = {}
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def on_event(self, event_name: str, callback: Callable[..., Any]) -> None:
        self._handlers.setdefault(event_name, []).append(callback)

    def off_event(self, event_name: str, callback: Callable[..., Any]) -> None:
        handlers = self._handlers.get(event_name, [])
        if callback in handlers:
            handlers.remove(callback)

    async def call(self, method: str, params: dict[str, Any] | None = None, *, timeout: float = 30.0) -> dict[str, Any]:
        _ = timeout
        self.calls.append((method, params))
        for cb in list(self._handlers.get("chat.message_update", [])):
            result = cb({"delta": "hi"})
            if hasattr(result, "__await__"):
                await result
        for cb in list(self._handlers.get("chat.tool_start", [])):
            result = cb({"name": "shell", "toolCallId": "t1"})
            if hasattr(result, "__await__"):
                await result
        for cb in list(self._handlers.get("chat.tool_end", [])):
            result = cb({"name": "shell", "toolCallId": "t1", "result": {"content": "ok"}})
            if hasattr(result, "__await__"):
                await result
        return {"ok": True}


@pytest.mark.asyncio
async def test_chat_send_registers_expected_ui_events() -> None:
    client = _FakeGatewayClient()
    deltas: list[str] = []
    tools: list[str] = []
    await chat_send(client, "hello")

    subscribed = set(client._handlers.keys())
    assert "chat.message_update" in subscribed
    assert "chat.tool_start" in subscribed
    assert "chat.tool_end" in subscribed
    assert "chat.error" in subscribed

    assert client.calls
    method, payload = client.calls[-1]
    assert method == "chat.send"
    assert isinstance(payload, dict)
    assert payload.get("message") == "hello"
    # Ensure handler registration does not leak after chat_send completes.
    for handlers in client._handlers.values():
        assert handlers == []

    await chat_send(
        client,
        "hello",
        on_delta=lambda d: deltas.append(d),
        on_tool_start=lambda n, _tid: tools.append(f"{n}:start"),
        on_tool_end=lambda n, _res, _err: tools.append(f"{n}:end"),
    )
    assert "hi" in deltas
    assert "shell:start" in tools
    assert "shell:end" in tools
