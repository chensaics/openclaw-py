"""Phase 41 tests — usage/cost loop, gateway wiring, models probe wiring."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from pyclaw.auto_reply.commands_core import handle_usage
from pyclaw.auto_reply.commands_registry import CommandContext
from pyclaw.auto_reply.commands_registry import ParsedCommand
from pyclaw.cli.app import app
from pyclaw.gateway.server import create_gateway_app
from pyclaw.infra.session_cost import aggregate_usage
from pyclaw.infra.session_cost import record_usage


runner = CliRunner()


def test_record_and_aggregate_usage(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYCLAW_STATE_DIR", str(tmp_path))
    record_usage(
        session_id="s1",
        provider="openai",
        model="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        has_api_key=True,
    )
    record_usage(
        session_id="s2",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        input_tokens=200,
        output_tokens=120,
        has_api_key=True,
    )

    usage = aggregate_usage(days=7)
    assert usage["sessions"] == 2
    assert usage["calls"] == 2
    assert usage["total_tokens"] == 470
    assert "openai" in usage["by_provider"]
    assert "gpt-4o" in usage["by_model"]


def test_status_usage_json_output(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYCLAW_STATE_DIR", str(tmp_path))
    record_usage(
        session_id="s-main",
        provider="openai",
        model="gpt-4o",
        input_tokens=321,
        output_tokens=123,
        has_api_key=True,
    )
    result = runner.invoke(app, ["status", "--json", "--usage"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "usage" in payload
    assert payload["usage"]["total_tokens"] == 444
    assert "openai" in payload["usage"]["by_provider"]


def test_gateway_registration_includes_extended_and_exec_methods() -> None:
    server = create_gateway_app()
    for method in ("usage.get", "exec.approve", "exec.deny", "browser.status"):
        assert method in server._handlers


@pytest.mark.asyncio
async def test_usage_get_handler_returns_aggregated_payload(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYCLAW_STATE_DIR", str(tmp_path))
    record_usage(
        session_id="s-gw",
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=50,
        output_tokens=20,
        has_api_key=True,
    )
    server = create_gateway_app()

    captured: dict[str, object] = {}

    class FakeConn:
        async def send_ok(self, method: str, payload: dict[str, object]) -> None:
            captured["method"] = method
            captured["payload"] = payload

    handler = server._handlers["usage.get"]
    await handler({"days": 7}, FakeConn())
    assert captured["method"] == "usage.get"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["totalTokens"] == 70
    assert "openai" in payload["byProvider"]


def test_models_probe_and_auth_overview_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    probe = runner.invoke(
        app,
        [
            "models",
            "probe",
            "--model",
            "gpt-4o",
            "--provider",
            "openai",
            "--api-key",
            "sk-test-value",
            "--json",
        ],
    )
    assert probe.exit_code == 0
    probe_payload = json.loads(probe.stdout)
    assert probe_payload["available"] is True

    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-value")
    auth = runner.invoke(app, ["models", "auth-overview", "--json"])
    assert auth.exit_code == 0
    auth_payload = json.loads(auth.stdout)
    assert any(entry["provider"] == "openai" and entry["configured"] for entry in auth_payload)


@pytest.mark.asyncio
async def test_usage_command_mode_and_cost_gate() -> None:
    set_mode = await handle_usage(
        CommandContext(
            command=ParsedCommand(name="usage", args=["full"], raw_args="full"),
        )
    )
    assert set_mode.metadata.get("action") == "set_usage_mode"
    assert set_mode.metadata.get("mode") == "full"

    oauth_view = await handle_usage(
        CommandContext(
            command=ParsedCommand(name="usage", args=[], raw_args=""),
            metadata={
                "usage_info": {
                    "session_tokens": 1000,
                    "input_tokens": 600,
                    "output_tokens": 400,
                    "estimated_cost_value": 0.42,
                    "auth_type": "oauth",
                }
            },
        )
    )
    assert "Session tokens" in oauth_view.text
    assert "Estimated cost" not in oauth_view.text
