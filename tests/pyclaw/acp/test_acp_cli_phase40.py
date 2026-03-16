"""Phase 40 tests — ACP CLI + session mapping production behavior."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from pyclaw.acp.client import _build_server_command
from pyclaw.acp.server import AcpGatewayAgent
from pyclaw.acp.session_mapper import parse_session_meta
from pyclaw.cli.app import app
from pyclaw.cli.commands.acp_cmd import acp_client_command, acp_run_command

runner = CliRunner()


class _FakeWs:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, payload: str) -> None:
        self.sent.append(payload)


def test_parse_session_meta_with_cwd() -> None:
    hints = parse_session_meta({"sessionKey": "k1", "cwd": "/tmp/work"})
    assert hints.session_key == "k1"
    assert hints.cwd == "/tmp/work"


def test_acp_root_help_has_phase40_options() -> None:
    result = runner.invoke(app, ["acp", "--help"])
    assert result.exit_code == 0
    for opt in (
        "--url",
        "--token-file",
        "--password-file",
        "--session",
        "--session-label",
        "--require-existing",
        "--reset-session",
        "--no-prefix-cwd",
    ):
        assert opt in result.stdout


def test_acp_client_help_has_phase40_options() -> None:
    result = runner.invoke(app, ["acp", "client", "--help"])
    assert result.exit_code == 0
    for opt in (
        "--server",
        "--server-args",
        "--url",
        "--token-file",
        "--password-file",
        "--session",
        "--session-label",
        "--require-existing",
        "--reset-session",
        "--timeout",
    ):
        assert opt in result.stdout


def test_build_server_command_for_pyclaw() -> None:
    cmd = _build_server_command(
        server="pyclaw",
        server_args=[],
        gateway_url="ws://127.0.0.1:18789/ws",
        auth_token="tok",
        auth_password="pwd",
        session="agent-main",
        session_label="label-a",
        require_existing_session=True,
        reset_session=True,
        no_prefix_cwd=True,
        server_verbose=True,
    )
    assert cmd[:3] == [sys.executable, "-m", "pyclaw.acp.server"]
    joined = " ".join(cmd)
    assert "--auth-token tok" in joined
    assert "--auth-password pwd" in joined
    assert "--session agent-main" in joined
    assert "--session-label label-a" in joined
    assert "--require-existing-session" in joined
    assert "--reset-session" in joined
    assert "--no-prefix-cwd" in joined


def test_acp_run_command_reads_token_and_password_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token_file = tmp_path / "token.txt"
    token_file.write_text("token-123\n", encoding="utf-8")
    password_file = tmp_path / "password.txt"
    password_file.write_text("pw-123\n", encoding="utf-8")

    captured: dict[str, Any] = {}

    async def fake_serve(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("pyclaw.acp.server.serve_acp_gateway", fake_serve)

    acp_run_command(
        url="ws://gateway/ws",
        token_file=str(token_file),
        password_file=str(password_file),
        session="agent:main:main",
        session_label="support",
        require_existing=True,
        reset_session=True,
        no_prefix_cwd=True,
        verbose=True,
    )

    assert captured["gateway_url"] == "ws://gateway/ws"
    assert captured["auth_token"] == "token-123"
    assert captured["auth_password"] == "pw-123"
    assert captured["default_session_key"] == "agent:main:main"
    assert captured["default_session_label"] == "support"
    assert captured["require_existing_session"] is True
    assert captured["reset_session_default"] is True
    assert captured["prefix_cwd"] is False
    assert captured["verbose"] is True


@pytest.mark.asyncio
async def test_server_new_session_with_require_existing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PYCLAW_STATE_DIR", str(tmp_path))
    agent = AcpGatewayAgent(require_existing_session=True)

    async def fake_gateway_request(method: str, params: dict[str, Any]) -> dict[str, Any]:
        assert method == "sessions.resolve"
        assert params["key"] == "missing-session"
        return {}

    monkeypatch.setattr(agent, "_gateway_request", fake_gateway_request)

    with pytest.raises(ValueError):
        await agent.new_session({"sessionId": "s1", "_meta": {"sessionKey": "missing-session"}})


@pytest.mark.asyncio
async def test_server_session_label_mapping(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PYCLAW_STATE_DIR", str(tmp_path))
    agent = AcpGatewayAgent(default_session_label="inbox")

    first = await agent.new_session({"sessionId": "s-map-1"})
    assert first["sessionLabel"] == "inbox"
    second = await agent.new_session({"sessionId": "s-map-2", "_meta": {"sessionLabel": "inbox"}})
    assert second["sessionKey"] == first["sessionKey"]


@pytest.mark.asyncio
async def test_server_prompt_prefixes_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PYCLAW_STATE_DIR", str(tmp_path))
    agent = AcpGatewayAgent(prefix_cwd=True)
    agent._ws = _FakeWs()

    async def fake_gateway_request(method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(agent, "_gateway_request", fake_gateway_request)
    created = await agent.new_session({"sessionId": "s-cwd", "_meta": {"cwd": "/tmp/project"}})
    await agent.prompt({"sessionId": created["sessionId"], "text": "hello"})

    assert agent._ws.sent
    payload = json.loads(agent._ws.sent[-1])
    assert payload["method"] == "chat.send"
    assert payload["params"]["message"].startswith("[cwd:/tmp/project] ")


def test_acp_client_command_forwards_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    token_file = tmp_path / "token.txt"
    token_file.write_text("token-x\n", encoding="utf-8")

    captured: dict[str, Any] = {}

    class _DummyClient:
        async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
            return {"ok": True, "method": method, "params": params}

        async def close(self) -> None:
            return None

    async def fake_create_acp_client(**kwargs: Any) -> _DummyClient:
        captured.update(kwargs)
        return _DummyClient()

    monkeypatch.setattr("pyclaw.acp.client.create_acp_client", fake_create_acp_client)

    acp_client_command(
        cwd="/tmp",
        server="pyclaw",
        server_args=["acp"],
        url="ws://gateway/ws",
        token_file=str(token_file),
        session="agent:main:main",
        session_label="support",
        require_existing=True,
        reset_session=True,
        no_prefix_cwd=True,
        timeout=15,
        server_verbose=True,
        verbose=True,
    )

    assert captured["cwd"] == "/tmp"
    assert captured["server"] == "pyclaw"
    assert captured["server_args"] == ["acp"]
    assert captured["gateway_url"] == "ws://gateway/ws"
    assert captured["auth_token"] == "token-x"
    assert captured["session"] == "agent:main:main"
    assert captured["session_label"] == "support"
    assert captured["require_existing_session"] is True
    assert captured["reset_session"] is True
    assert captured["no_prefix_cwd"] is True
    assert captured["request_timeout_s"] == 15.0
