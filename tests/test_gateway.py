"""Tests for the gateway server — protocol frames, handlers, and WebSocket flow."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pyclaw.gateway.protocol.frames import (
    PROTOCOL_VERSION,
    ErrorShape,
    EventFrame,
    RequestFrame,
    ResponseFrame,
)
from pyclaw.gateway.server import GatewayServer, create_gateway_app


# ---------- Protocol frames ----------


def test_request_frame_from_dict():
    data = {"type": "req", "id": "r1", "method": "health", "params": {"a": 1}}
    frame = RequestFrame.from_dict(data)
    assert frame is not None
    assert frame.id == "r1"
    assert frame.method == "health"
    assert frame.params == {"a": 1}


def test_request_frame_invalid():
    assert RequestFrame.from_dict({"type": "res", "id": "r1"}) is None
    assert RequestFrame.from_dict({"type": "req"}) is None
    assert RequestFrame.from_dict({"type": "req", "id": "", "method": "x"}) is None


def test_response_frame_ok():
    frame = ResponseFrame.ok_response("r1", {"key": "value"})
    d = frame.to_dict()
    assert d["type"] == "res"
    assert d["id"] == "r1"
    assert d["ok"] is True
    assert d["payload"] == {"key": "value"}


def test_response_frame_error():
    frame = ResponseFrame.error_response("r1", "not_found", "Item not found")
    d = frame.to_dict()
    assert d["ok"] is False
    assert d["error"]["code"] == "not_found"
    assert d["error"]["message"] == "Item not found"


def test_event_frame():
    frame = EventFrame(event="chat.update", payload={"delta": "hi"}, seq=1)
    d = frame.to_dict()
    assert d["type"] == "event"
    assert d["event"] == "chat.update"
    assert d["seq"] == 1


def test_error_shape_to_dict():
    err = ErrorShape(code="timeout", message="Timed out", retryable=True, retry_after_ms=5000)
    d = err.to_dict()
    assert d["code"] == "timeout"
    assert d["retryable"] is True
    assert d["retryAfterMs"] == 5000


# ---------- HTTP health endpoint ----------


def test_health_endpoint():
    server = create_gateway_app()
    client = TestClient(server.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["protocol"] == PROTOCOL_VERSION


# ---------- WebSocket flow ----------


def _ws_send(ws, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send a request frame and receive the response."""
    frame = {"type": "req", "id": method, "method": method}
    if params:
        frame["params"] = params
    ws.send_json(frame)
    return ws.receive_json()


def test_ws_connect_no_auth():
    """Connect without auth token should succeed when server has no token."""
    server = create_gateway_app()
    client = TestClient(server.app)

    with client.websocket_connect("/") as ws:
        resp = _ws_send(ws, "connect", {"clientName": "test"})
        assert resp["ok"] is True
        assert resp["payload"]["protocol"] == PROTOCOL_VERSION


def test_ws_connect_with_auth():
    """Connect with correct token should succeed."""
    server = create_gateway_app(auth_token="secret123")
    client = TestClient(server.app)

    with client.websocket_connect("/") as ws:
        resp = _ws_send(ws, "connect", {
            "clientName": "test",
            "auth": {"token": "secret123"},
        })
        assert resp["ok"] is True


def test_ws_connect_bad_auth():
    """Connect with wrong token should fail."""
    server = create_gateway_app(auth_token="secret123")
    client = TestClient(server.app)

    with client.websocket_connect("/") as ws:
        resp = _ws_send(ws, "connect", {
            "clientName": "test",
            "auth": {"token": "wrong"},
        })
        assert resp["ok"] is False
        assert resp["error"]["code"] == "auth_failed"


def test_ws_must_connect_first():
    """Sending a method before connect should be rejected."""
    server = create_gateway_app()
    client = TestClient(server.app)

    with client.websocket_connect("/") as ws:
        resp = _ws_send(ws, "health")
        assert resp["ok"] is False
        assert resp["error"]["code"] == "auth_required"


def test_ws_health_after_connect():
    server = create_gateway_app()
    client = TestClient(server.app)

    with client.websocket_connect("/") as ws:
        _ws_send(ws, "connect", {"clientName": "test"})
        resp = _ws_send(ws, "health")
        assert resp["ok"] is True
        assert "version" in resp["payload"]


def test_ws_unknown_method():
    server = create_gateway_app()
    client = TestClient(server.app)

    with client.websocket_connect("/") as ws:
        _ws_send(ws, "connect", {"clientName": "test"})
        resp = _ws_send(ws, "nonexistent.method")
        assert resp["ok"] is False
        assert resp["error"]["code"] == "unknown_method"


# ---------- Config handlers ----------


def test_ws_config_get(tmp_path: Path):
    config_file = tmp_path / "pyclaw.json"
    config_file.write_text('{}')

    server = create_gateway_app(config_path=str(config_file))
    client = TestClient(server.app)

    with client.websocket_connect("/") as ws:
        _ws_send(ws, "connect", {"clientName": "test"})
        resp = _ws_send(ws, "config.get")
        assert resp["ok"] is True
        assert "config" in resp["payload"]


def test_ws_config_get_missing(tmp_path: Path):
    server = create_gateway_app(config_path=str(tmp_path / "nope.json"))
    client = TestClient(server.app)

    with client.websocket_connect("/") as ws:
        _ws_send(ws, "connect", {"clientName": "test"})
        resp = _ws_send(ws, "config.get")
        assert resp["ok"] is True
        assert resp["payload"]["config"] == {}


# ---------- Sessions handlers ----------


def test_ws_sessions_list(tmp_path: Path, monkeypatch):
    # Set up a fake agents directory
    agent_dir = tmp_path / "agents" / "main" / "sessions"
    agent_dir.mkdir(parents=True)
    (agent_dir / "test.jsonl").write_text('{"type":"session","id":"s1"}\n')

    # Patch the underlying paths module that sessions.py imports from at call time
    monkeypatch.setattr(
        "pyclaw.config.paths.resolve_agents_dir",
        lambda state_dir=None: tmp_path / "agents",
    )

    server = create_gateway_app()
    client = TestClient(server.app)

    with client.websocket_connect("/") as ws:
        _ws_send(ws, "connect", {"clientName": "test"})
        resp = _ws_send(ws, "sessions.list")
        assert resp["ok"] is True
        assert len(resp["payload"]["sessions"]) == 1
        assert resp["payload"]["sessions"][0]["agentId"] == "main"


def test_ws_sessions_preview(tmp_path: Path):
    session_file = tmp_path / "test.jsonl"
    lines = [
        json.dumps({"type": "session", "id": "s1"}),
        json.dumps({"type": "message", "message": {"role": "user", "content": "Hello"}}),
        json.dumps({"type": "message", "message": {"role": "assistant", "content": "Hi!"}}),
    ]
    session_file.write_text("\n".join(lines) + "\n")

    server = create_gateway_app()
    client = TestClient(server.app)

    with client.websocket_connect("/") as ws:
        _ws_send(ws, "connect", {"clientName": "test"})
        resp = _ws_send(ws, "sessions.preview", {"path": str(session_file)})
        assert resp["ok"] is True
        assert len(resp["payload"]["messages"]) == 2
        assert resp["payload"]["messages"][0]["role"] == "user"
