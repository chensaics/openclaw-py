"""Phase 42 tests — browser CLI and gateway RPC alignment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from pyclaw.cli.app import app
from pyclaw.gateway.methods.browser_methods import create_browser_handlers
from pyclaw.gateway.server import create_gateway_app

runner = CliRunner()


class _FakeConn:
    def __init__(self) -> None:
        self.ok_calls: list[tuple[str, dict[str, Any]]] = []
        self.err_calls: list[tuple[str, str, str]] = []

    async def send_ok(self, method: str, payload: dict[str, Any]) -> None:
        self.ok_calls.append((method, payload))

    async def send_error(self, method: str, code: str, message: str) -> None:
        self.err_calls.append((method, code, message))


def test_gateway_registration_includes_browser_methods() -> None:
    server = create_gateway_app()
    for method in (
        "browser.status",
        "browser.start",
        "browser.stop",
        "browser.tabs",
        "browser.open",
        "browser.navigate",
        "browser.click",
        "browser.type",
        "browser.screenshot",
        "browser.snapshot",
        "browser.evaluate",
    ):
        assert method in server._handlers


@pytest.mark.asyncio
async def test_browser_navigation_blocked_by_ssrf_policy() -> None:
    handlers = create_browser_handlers()
    conn = _FakeConn()
    await handlers["browser.navigate"]({"profile": "pyclaw", "url": "http://127.0.0.1/admin"}, conn)
    assert conn.err_calls
    assert conn.err_calls[0][0] == "browser.navigate"
    assert conn.err_calls[0][1] in ("blocked", "invalid_state")


@pytest.mark.asyncio
async def test_browser_open_tabs_snapshot_flow() -> None:
    handlers = create_browser_handlers()
    conn = _FakeConn()

    await handlers["browser.start"]({"profile": "pyclaw"}, conn)
    await handlers["browser.open"]({"profile": "pyclaw", "url": "https://docs.openclaw.ai"}, conn)
    await handlers["browser.tabs"]({"profile": "pyclaw"}, conn)
    await handlers["browser.snapshot"]({"profile": "pyclaw"}, conn)

    all_methods = [m for m, _ in conn.ok_calls] + [m for m, _, _ in conn.err_calls]
    assert "browser.start" in all_methods
    assert "browser.open" in all_methods
    assert "browser.tabs" in all_methods
    assert "browser.snapshot" in all_methods


def test_browser_root_help_exposes_global_rpc_flags() -> None:
    result = runner.invoke(app, ["browser", "--help"])
    assert result.exit_code == 0
    for opt in ("--url", "--token", "--password", "--timeout", "--browser-profile", "--json"):
        assert opt in result.stdout


def test_browser_cli_status_routes_to_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_browser_rpc_sync(
        method: str,
        params: dict[str, Any],
        *,
        gateway_url: str,
        token: str | None,
        password: str | None,
        timeout_ms: int,
    ) -> dict[str, Any]:
        captured.update(
            {
                "method": method,
                "params": params,
                "gateway_url": gateway_url,
                "token": token,
                "password": password,
                "timeout_ms": timeout_ms,
            }
        )
        return {
            "started": True,
            "profile": params.get("profile", "pyclaw"),
            "tabCount": 1,
            "activeUrl": "https://example.com",
        }

    monkeypatch.setattr("pyclaw.cli.commands.browser_cmd._browser_rpc_sync", fake_browser_rpc_sync)
    result = runner.invoke(
        app,
        [
            "browser",
            "--url",
            "ws://127.0.0.1:18789",
            "--token",
            "token-value",
            "--timeout",
            "5000",
            "--json",
            "status",
        ],
    )
    assert result.exit_code == 0
    assert '"started": true' in result.stdout
    assert captured["method"] == "browser.status"
    assert captured["params"]["profile"] == "pyclaw"
    assert captured["gateway_url"] == "ws://127.0.0.1:18789"
    assert captured["token"] == "token-value"
    assert captured["timeout_ms"] == 5000


def test_browser_cli_screenshot_writes_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"screenshotB64": "aGVsbG8="}  # "hello"

    def fake_browser_rpc_sync(
        method: str,
        params: dict[str, Any],
        *,
        gateway_url: str,
        token: str | None,
        password: str | None,
        timeout_ms: int,
    ) -> dict[str, Any]:
        assert method == "browser.screenshot"
        return dict(payload)

    monkeypatch.setattr("pyclaw.cli.commands.browser_cmd._browser_rpc_sync", fake_browser_rpc_sync)
    out = tmp_path / "shot.bin"
    result = runner.invoke(app, ["browser", "screenshot", "--out", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert out.read_bytes() == b"hello"
