"""Phase 44 tests — Gateway CLI subcommands, logs RPC, pyclaw naming, browser dedup."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from pyclaw.cli.app import app

runner = CliRunner()
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 44a: Gateway subcommand tree
# ---------------------------------------------------------------------------


class TestGatewaySubcommands:
    """Verify gateway subcommand surface exists and accepts correct args."""

    def test_gateway_help_shows_subcommands(self) -> None:
        result = runner.invoke(app, ["gateway", "--help"])
        assert result.exit_code == 0
        for sub in ("run", "status", "probe", "call", "discover"):
            assert sub in result.stdout

    def test_gateway_status_help(self) -> None:
        result = runner.invoke(app, ["gateway", "status", "--help"])
        assert result.exit_code == 0
        for flag in ("--url", "--token", "--timeout", "--no-probe", "--deep", "--json"):
            assert flag in result.stdout

    def test_gateway_probe_help(self) -> None:
        result = runner.invoke(app, ["gateway", "probe", "--help"])
        assert result.exit_code == 0
        for flag in ("--url", "--token", "--timeout", "--json"):
            assert flag in result.stdout

    def test_gateway_call_help(self) -> None:
        result = runner.invoke(app, ["gateway", "call", "--help"])
        assert result.exit_code == 0
        assert "--params" in result.stdout
        assert "METHOD" in result.stdout.upper() or "method" in result.stdout.lower()

    def test_gateway_discover_help(self) -> None:
        result = runner.invoke(app, ["gateway", "discover", "--help"])
        assert result.exit_code == 0
        for flag in ("--timeout", "--json"):
            assert flag in result.stdout

    def test_gateway_status_no_probe_json(self) -> None:
        result = runner.invoke(app, ["gateway", "status", "--no-probe", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "service" in data
        assert data["service"]["status"] in ("running", "stopped")

    def test_gateway_discover_json_no_crash(self) -> None:
        result = runner.invoke(app, ["gateway", "discover", "--json", "--timeout", "100"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "beacons" in data


# ---------------------------------------------------------------------------
# 44b: Logs RPC method
# ---------------------------------------------------------------------------


class TestLogsRPC:
    """Verify logs.tail RPC handler registration and behavior."""

    def test_logs_handlers_registered(self) -> None:
        from pyclaw.gateway.methods.logs_methods import create_logs_handlers

        handlers = create_logs_handlers()
        assert "logs.tail" in handlers

    @pytest.mark.asyncio
    async def test_logs_tail_empty(self, tmp_path: Path) -> None:
        from pyclaw.gateway.methods.logs_methods import create_logs_handlers

        handlers = create_logs_handlers()
        handler = handlers["logs.tail"]

        responses: list[tuple[str, dict]] = []

        class FakeConn:
            async def send_ok(self, method: str, payload: dict) -> None:
                responses.append((method, payload))

            async def send_error(self, method: str, code: str, msg: str) -> None:
                responses.append((method, {"error": code, "message": msg}))

        with patch("pyclaw.gateway.methods.logs_methods._resolve_log_path", return_value=tmp_path / "no.log"):
            await handler({"limit": 10}, FakeConn())

        assert len(responses) == 1
        assert responses[0][0] == "logs.tail"
        assert responses[0][1]["count"] == 0

    @pytest.mark.asyncio
    async def test_logs_tail_reads_lines(self, tmp_path: Path) -> None:
        from pyclaw.gateway.methods.logs_methods import create_logs_handlers

        log_file = tmp_path / "test.log"
        log_file.write_text("\n".join(f"line-{i}" for i in range(50)))

        handlers = create_logs_handlers()
        handler = handlers["logs.tail"]

        responses: list[tuple[str, dict]] = []

        class FakeConn:
            async def send_ok(self, method: str, payload: dict) -> None:
                responses.append((method, payload))

            async def send_error(self, method: str, code: str, msg: str) -> None:
                responses.append((method, {"error": code, "message": msg}))

        with patch("pyclaw.gateway.methods.logs_methods._resolve_log_path", return_value=log_file):
            await handler({"limit": 10}, FakeConn())

        assert responses[0][1]["count"] == 10
        assert "line-49" in responses[0][1]["lines"][-1]


# ---------------------------------------------------------------------------
# 44c: Logs CLI remote + local fallback
# ---------------------------------------------------------------------------


class TestLogsCLI:
    """Verify logs command tries RPC then falls back to local file."""

    def test_logs_help(self) -> None:
        result = runner.invoke(app, ["logs", "--help"])
        assert result.exit_code == 0
        for flag in ("--follow", "--limit", "--json", "--local-time"):
            assert flag in result.stdout

    def test_logs_fallback_local_no_crash(self, tmp_path: Path) -> None:
        with (
            patch("pyclaw.cli.commands.logs_cmd._try_rpc_tail", return_value=None),
            patch("pyclaw.cli.commands.logs_cmd.resolve_state_dir", return_value=tmp_path),
        ):
            result = runner.invoke(app, ["logs"])
        assert result.exit_code == 0

    def test_logs_rpc_success_path(self) -> None:
        fake_lines = ["log-line-1", "log-line-2"]
        with patch("pyclaw.cli.commands.logs_cmd._try_rpc_tail", return_value=fake_lines):
            result = runner.invoke(app, ["logs"])
        assert result.exit_code == 0
        assert "log-line-1" in result.stdout
        assert "log-line-2" in result.stdout


# ---------------------------------------------------------------------------
# 44d: pyclaw naming convergence
# ---------------------------------------------------------------------------


class TestPyclawNaming:
    """Ensure all user-facing text uses pyclaw, not openclaw."""

    @pytest.mark.parametrize(
        "filepath",
        [
            "src/pyclaw/cli/commands/config_cmd.py",
            "src/pyclaw/cli/commands/setup.py",
            "src/pyclaw/cli/commands/auth_cmd.py",
            "src/pyclaw/cli/commands/doctor.py",
            "src/pyclaw/cli/commands/doctor_flows.py",
            "src/pyclaw/cli/commands/onboarding_enhanced.py",
            "src/pyclaw/cli/commands/message_cmd.py",
        ],
    )
    def test_no_openclaw_in_user_text(self, filepath: str) -> None:
        full = PROJECT_ROOT / filepath
        if not full.exists():
            pytest.skip(f"{filepath} not found")
        content = full.read_text(encoding="utf-8")
        # Scan for user-facing 'openclaw' CLI references in strings
        for i, line in enumerate(content.splitlines(), 1):
            if "pyclaw" in line.lower():
                # Skip module imports, paths, and non-string references
                stripped = line.strip()
                if stripped.startswith(("import ", "from ", "#")):
                    continue
                if "pyclaw." in stripped and ("'" not in stripped and '"' not in stripped):
                    continue
                # Check for quoted user-facing text containing 'openclaw' as a command
                for quote_char in ("'", '"'):
                    if f"{quote_char}openclaw " in stripped or "'openclaw " in stripped:
                        pytest.fail(f"{filepath}:{i} still references 'openclaw' in user text: {stripped}")


# ---------------------------------------------------------------------------
# 44e: extended.py browser placeholder removal
# ---------------------------------------------------------------------------


class TestExtendedBrowserDedup:
    """Verify browser.status/browser.navigate no longer in extended handlers."""

    def test_extended_no_browser_keys(self) -> None:
        from pyclaw.gateway.methods.extended import create_extended_handlers

        handlers = create_extended_handlers()
        assert "browser.status" not in handlers
        assert "browser.navigate" not in handlers

    def test_browser_methods_still_registered(self) -> None:
        from pyclaw.gateway.methods.browser_methods import create_browser_handlers

        handlers = create_browser_handlers()
        assert "browser.status" in handlers


# ---------------------------------------------------------------------------
# Registration ordering
# ---------------------------------------------------------------------------


class TestRegistrationOrder:
    """Verify logs.tail is registered and browser is authoritative."""

    def test_logs_tail_in_registration(self) -> None:
        from pyclaw.gateway.methods.logs_methods import create_logs_handlers

        h = create_logs_handlers()
        assert "logs.tail" in h


# ---------------------------------------------------------------------------
# Regression: gateway help still shows in root
# ---------------------------------------------------------------------------


class TestRootRegression:
    """Phase 39+ regression: gateway subcommand visible in root help."""

    def test_root_help_shows_gateway(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "gateway" in result.stdout
