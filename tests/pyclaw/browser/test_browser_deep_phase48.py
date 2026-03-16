"""Phase 48 tests — browser profiles, focus, close subcommands."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from pyclaw.cli.app import app

runner = CliRunner()


class TestBrowserDeepCommands:
    """Verify new browser subcommands exist and accept proper args."""

    def test_browser_help_shows_new_commands(self) -> None:
        result = runner.invoke(app, ["browser", "--help"])
        assert result.exit_code == 0
        for cmd in ("profiles", "create-profile", "delete-profile", "focus", "close"):
            assert cmd in result.stdout

    def test_profiles_help(self) -> None:
        result = runner.invoke(app, ["browser", "profiles", "--help"])
        assert result.exit_code == 0

    def test_create_profile_help(self) -> None:
        result = runner.invoke(app, ["browser", "create-profile", "--help"])
        assert result.exit_code == 0
        assert "NAME" in result.stdout.upper() or "name" in result.stdout.lower()

    def test_delete_profile_help(self) -> None:
        result = runner.invoke(app, ["browser", "delete-profile", "--help"])
        assert result.exit_code == 0

    def test_focus_help(self) -> None:
        result = runner.invoke(app, ["browser", "focus", "--help"])
        assert result.exit_code == 0
        assert "TAB" in result.stdout.upper() or "tab" in result.stdout.lower()

    def test_close_help(self) -> None:
        result = runner.invoke(app, ["browser", "close", "--help"])
        assert result.exit_code == 0

    def test_profiles_via_mock_rpc(self) -> None:
        mock_payload = {"profiles": ["default", "dev"], "count": 2}
        with patch("pyclaw.cli.commands.browser_cmd._browser_rpc_sync", return_value=mock_payload):
            result = runner.invoke(app, ["browser", "--json", "profiles"])
        assert result.exit_code == 0, result.stdout
        import json

        data = json.loads(result.stdout)
        assert data["count"] == 2

    def test_focus_via_mock_rpc(self) -> None:
        mock_payload = {"ok": True, "tabId": "tab-1"}
        with patch("pyclaw.cli.commands.browser_cmd._browser_rpc_sync", return_value=mock_payload):
            result = runner.invoke(app, ["browser", "focus", "tab-1"])
        assert result.exit_code == 0
        assert "tab-1" in result.stdout

    def test_close_via_mock_rpc(self) -> None:
        mock_payload = {"ok": True, "tabId": "tab-2"}
        with patch("pyclaw.cli.commands.browser_cmd._browser_rpc_sync", return_value=mock_payload):
            result = runner.invoke(app, ["browser", "close", "tab-2"])
        assert result.exit_code == 0
        assert "tab-2" in result.stdout


class TestBrowserOriginalRegression:
    """Ensure existing browser commands still work."""

    def test_browser_status_help(self) -> None:
        result = runner.invoke(app, ["browser", "status", "--help"])
        assert result.exit_code == 0

    def test_browser_tabs_help(self) -> None:
        result = runner.invoke(app, ["browser", "tabs", "--help"])
        assert result.exit_code == 0

    def test_browser_open_help(self) -> None:
        result = runner.invoke(app, ["browser", "open", "--help"])
        assert result.exit_code == 0
